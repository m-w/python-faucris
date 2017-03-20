# -*- coding: utf-8 -*-

"""
Class for webservice access of FAU-CRIS (current research information system of
Friedrich-Alexander-Universität Erlangen-Nürnberg)

@author: Marcus Walther
@contact: cris-support@fau.de
"""

import collections
from urllib import request as urllib_request

from lxml import etree

SORT_ASC = 1
SORT_DESC = 2


class FauCris:
    def __init__(self):
        self.base = "https://cris.fau.de/ws-cached/1.0/public/infoobject/"

    @staticmethod
    def open(url):
        """
        return connection for reading. respects redirects.

        :param url: address to fetch from
        :return: raw data (unicode)
        """

        response = urllib_request.urlopen(url)
        if response.getcode() != 200:
            raise Exception("unsuccessful request")

        return response

    def get(self, identifier, selector=None):
        """
        issue single request for raw data and parse structure

        :param identifier: denotes additional request parameters (url parts)
        :param selector: filter object (currently not used)
        :return: root element of xml (etree)
        """
        try:
            xml = etree.parse(self.open(self.base + identifier))
        except Exception as e:
            raise Exception("request failed: " + ", ".join(e.args))

        return xml.getroot()

    def retrieve(self, reqs, _class, selector=None):
        """
        fetch and merge data from webservice; result list contains only unique
        data sets.

        :param reqs: list of url selectors
        :param _class: class of result
        :param selector: filter class
        :return: list of data objects
        """

        # create selector if not done before
        if selector is not None and not isinstance(selector, Selector):
            selector = Selector(selector)

        data = []
        for _r in reqs:
            try:
                _x = self.get(_r, selector)
            except:
                continue
            data.append(_x)

        result = {}
        for _x in data:
            # split into single datasets
            try:
                _l = _x.xpath(_class.xpath)
            except:
                raise Exception("invalid xml data or xpath")

            # generate classes out of each dataset
            for _s in _l:
                dataset = _class(_s)

                # unique list by id of dataset
                # apply filter is defined
                if dataset['id'] and (selector is None or selector.evaluate(dataset)):
                    result[dataset['id']] = dataset

        return result

    def _fetch(self, name, class_, request_templates, ids=None, selector=None):
        """
        helper method for requesting data.

        :param name: name used for error messages
        :param class_: class for data parsing
        :param request_templates: templates for requests
        :param ids: id data for template (will be fed to _parseId method)
        :param selector: filter operator
        :return: data objects
        """

        if ids is None or ids == '0':
            raise Exception("Please supply valid id for %s." % name)

        idlist = self._parseId(ids)

        reqs = []
        for _i in idlist:
            try:
                _i = int(_i)
            except ValueError:
                raise Exception("invalid %s id number" % name)

            for t in request_templates:
                reqs.append(t % _i)

        response = self.retrieve(reqs, class_, selector)
        return response

    @staticmethod
    def _parseId(idvalue):
        """
        Process id for multiple values

        :param idvalue: iterable, text or integer
        :return: list of ids
        """

        # just number
        if type(idvalue) == int:
            return [idvalue]

        # text
        if type(idvalue) == str:
            # list of ids
            if ',' in idvalue:
                return [_i.strip() for _i in idvalue.split(',')]
            else:
                # just text
                return [idvalue]

        return idvalue


class Publications(FauCris):
    """
    handle publication requests
    """
    def __init__(self):
        super(Publications, self).__init__()

    def by_orga(self, id_=None, selector=None, disable_orga_check=False):
        """
        Fetch publications using an auto-relation and additional direct relation
        denoted by organization id(s).

        :param id_: orga id information (int, string, list, ...)
        :param selector: filter operator
        :return: list of Publication classes
        """

        # check if orga is not on (sub-)root level
        if not disable_orga_check:
            template = ['get/Organisation/%d']
            orgas = self._fetch('organization', Organization, template, id_)

            for _, _o in orgas.items():
                if _o['fau_org_nr'].endswith('000000'):
                    raise ValueError(
                              'root and subroot level organization not allowed')

        template = [
            "getautorelated/Organisation/%d/ORGA_2_PUBL_1",
            "getrelated/Organisation/%d/Publ_has_ORGA",
        ]
        publs = self._fetch('organization', Publication, template, id_, selector)
        return publs

    def by_id(self, id_=None):
        """
        Fetch publications denoted by their id(s). A selector is not supported
        here because it makes not sense.

        :param id_: publication id information (int, string, list, ...)
        :return: list of Publication classes
        """
        template = ['get/Publication/%d']
        publs = self._fetch('publication', Publication, template, id_)
        return publs

    def by_pers(self, id_=None, selector=None):
        """
        Fetch publications denoted by author id(s).

        :param id_: author id information (int, string, list, ...)
        :param selector: filter operator
        :return: list of Publication classes
        """
        template = ['getautorelated/Person/%d/PERS_2_PUBL_1']
        publs = self._fetch('person', Publication, template, id_, selector)
        return publs


class CrisEntity:
    """
    CRIS webservice entity.
    """
    def __init__(self, initial_data=None):
        if initial_data is None:
            return

        data = {}

        # attribute mapping
        for _i in ['id', 'createdOn', 'updatedOn']:
            data[_i.lower()] = initial_data.get(_i)

        # value mapping
        for _c in initial_data.getchildren():
            # skip "relation", etc.
            if _c.tag.lower() != 'attribute':
                continue

            name = _c.get("name").lower()
            if _c.get("language") == '1':
                name += '_en'

            if _c.get("disposition") == 'choicegroup':
                try:
                    value = _c.xpath('./additionalInfo')[0].text
                except:
                    value = None
            else:
                value = _c.xpath('./data')[0].text

            data[name] = value

        self._data = data

    def __getitem__(self, item):
        return self._data.get(item)


class Organization(CrisEntity):
    """
    Single organization object
    """
    xpath = "//infoObject[@type='Organisation']"

    def __init__(self, initial_data=None):
        super(Organization, self).__init__(initial_data)


class Publication(CrisEntity):
    """
    Single publication object
    """
    xpath = "//infoObject[@type='Publication']"

    def __init__(self, initial_data=None):
        super(Publication, self).__init__(initial_data)

    def __repr__(self):
        try:
            t = ' (%s: %s%s)' % (
                self._data['publyear'],
                self._data['cftitle'][:50],
                len(self._data['cftitle']) > 50 and '...' or ''
            )
        except:
            t = ''
        try:
            return 'CRIS publication #%s%s' % (self._data['id'], t)
        except KeyError:
            return 'Publication object (%d)' % id(self)

    def toBibTeX(self, mask_caps=True):
        """
        Returns BibTeX code for this publication.

        :param {boolean} mask_caps Flag for masking capital letters in the
                                    publications' title (default: true)
        :return: {string} BibTeX data
        """
        try:
            import bibtexparser
        except ImportError:
            raise Exception('Please install "bibtexparser" module!')

        # map basic attributes
        # map type
        data = self._data
        # from pprint import pprint
        # pprint(data)
        publtype = data['publication type'].lower()
        types = {
            'journal article': 'article',
            'book': 'book',
            'editorial': 'book',
            'article in edited volumes': 'incollection',
            'conference contribution': 'inproceedings',
            # use subtypes
            'thesis': {
                'Dissertation': 'phdthesis',
                'Masterarbeit': 'masterthesis',
                'Diplomarbeit': 'masterthesis',
            },
        }

        # sub types ...
        if publtype == 'thesis':
            bibtype = types.get(publtype).get(data['publication thesis subtype'], 'misc')
        else:
            bibtype = types.get(publtype, 'misc')

        # valid for all types
        bibdata = {
            'id': 'faucris.%s' % (data['id']),
            'type': bibtype,
            'year': data['publyear'],
            'title': data['cftitle'],
            'note': data['note'],
            'keywords': data['keywords'],
            'abstract': data['cfabstr'],
            'month': data['monthcg'],
            'url': data['cfuri'],
            'peerreviewed': data['peerreviewed'],
            'faupublication': data['fau publikation'],
            'doi': data['doi'],
        }
        if bibdata['abstract'] is not None and bibdata['abstract'].startswith('<p>'):
            bibdata['abstract'] = bibdata['abstract'][3:-6].strip()

        # type dependent
        if bibdata['type'] in ('article'):
            bibdata['journal'] = data['journalname']
            bibdata['volume'] = data['book volume']
            bibdata['pages'] = data['pagesrange']

        if bibdata['type'] in ('book', 'incollection', 'editorial', 'inproceedings'):
            bibdata['publisher'] = data['publisher']
            bibdata['editor'] = data['editor']
            bibdata['isbn'] = data['cfisbn']
            bibdata['volume'] = data['book volume']
            bibdata['series'] = data['cfseries']
            bibdata['edition'] = data['cfedition']
            bibdata['address'] = data['cfcitytown']
            bibdata['pages'] = data['pagesrange']

        if bibdata['type'] in ('incollection'):
            bibdata['booktitle'] = data['edited volumes']

        if bibdata['type'] in ('inproceedings') or \
                (bibdata['type'] in ('unpublished') and data['futurepublicationtype'].lower() == 'conference contribution'):
            bibdata['booktitle'] = data['conference proceedings title']
            # try to use conference name as fall-back
            if bibdata['booktitle'] is None or not len(bibdata['booktitle']):
                bibdata['booktitle'] = data['event title']
            bibdata['venue'] = data['event location']
            bibdata['date'] = data['event start date']
            if bibdata['date'] is not None and data['event end date'] is not None:
                bibdata['date'] += '/' + data['event end date']

        if bibdata['type'] in ('phdthesis', 'masterthesis'):
            bibdata['school'] = 'Friedrich-Alexander-Universität Erlangen-Nürnberg'

        if bibdata['type'] == 'unpublished' and not bibdata['note']:
            bibdata['note'] = \
                'https://cris.fau.de/converis/publicweb/Publication/%s' % data['id']

        try:
            author_editor = ' and '.join(
                ['%s, %s' % (_i, _j) for _i, _j in
                    [_k.split(':') for _k in data['exportauthors'].split('|')]
                ]
            )
        except AttributeError:
            # exportauthors is set non-live, so it may be missing
            # the dataset is incomplete, so there's no BibTeX output
            return ''

        # handle incomplete author/editor relation
        if data.get('complete author relations', None) is None:
            author_editor += " and et al."
            bibdata['support_note'] = 'Author relations incomplete. ' + \
                'You may find additional data in field \'author_hint\''
            bibdata['author_hint'] = data.get('srcauthors', '')

        if publtype == 'editorial':
            bibdata['editor'] = author_editor
        else:
            bibdata['author'] = author_editor

        # enclosing capital letters in title (default)
        if mask_caps:
            elements = re.findall('(\W+)?(\w+)(\W+)?', bibdata['title'])
            _t = ''
            for _i in elements:
                if not _i[1].islower() and not _i[1].isdigit():
                    _t += '%s{%s}%s' % _i
                else:
                    _t += '%s%s%s' % _i
            # remove double masks
            _t = _t.replace('{{', '{').replace('}}', '}')
            bibdata['title'] = _t

        bibdb = bibtexparser.bibdatabase.BibDatabase()

        # kick "None" attributes
        _n = {k: v for k, v in bibdata.items() if v is not None}
        bibdb.entries.append(_n)

        return bibtexparser.dumps(bibdb)


class Selector:
    """
    Filter object for CRIS data.
    """
    def __init__(self, criteria):
        """
        Parse filter operators.

        Operators are concatenated using __ (two underscores) to the attribute
        name in order to denote the filter, e.g. publyear__eq

        All python compare operators are supported. e.g. eq (equal), gt
        (greater), ge (greater equal), lt (lower), le (lower equal)
        http://www.diveintopython3.net/special-method-names.html#rich-comparisons

        All filters are expected as dictionary. Key is the filter, value is
        the reference, e.g. {"publyear__eq": 2015}.

        If more than one criteria is set, filters are combined using "AND".

        Comparison is done case-insensitive. All attributes are treated as
        strings.

        :param criteria: dictionary of selector attributes
        """

        flist = {}
        for k in criteria:
            # force lower case
            op = k.lower().split('__')

            if op[0] not in flist:
                flist[op[0]] = {}

            # change type
            v = str(criteria.get(k))
            flist[op[0]][op[1]] = v

        self.selectors = flist

    def evaluate(self, dataset):
        """
        Test pre-defined criteria against dataset

        :param dataset: something that ca be analyzed
        :return: True or False
        """

        for _a, _s in self.selectors.items():
            try:
                # cast to lower case string
                value = str(dataset[_a]).lower()
            except KeyError:
                # If attribute is not present, skip filter silently. This makes
                # the test successful and may be therefore a bad idea.
                continue

            for _o, _v in _s.items():
                method = getattr(value, '__%s__' % _o)
                if method(_v) is False:
                    return False

        return True


class Formatter:
    """
    Group and sort data in up to two levels. Method "execute" returns
    reformatted data.
    """
    def __init__(self, group_by, group_order=SORT_DESC, sort_by=None,
                 sort_order=SORT_ASC):
        """
        Method takes up to 4 arguments.

        :param group_by: attribute name for grouping datasets (use 'None' for
                         sorting only)
        :param group_order: SORT_ASC, SORT_DESC or list of values
        :param sort_by: attribute name for sorting inside groups
        :param sort_order: SORT_ASC or SORT_DESC
        """
        if group_by is not None:
            self.group_by = group_by.lower()
        else:
            self.group_by = None

        if group_order in (SORT_ASC, SORT_DESC):
            self.group_order = group_order
        else:
            self.group_order = [_i.lower() for _i in group_order]

        try:
            self.sort_by = sort_by.lower()
        except ValueError:
            self.sort_by = None

        if sort_order in (SORT_ASC, SORT_DESC):
            self.sort_order = sort_order
        else:
            self.sort_order = [_i.lower() for _i in sort_order]

    def execute(self, data):
        """
        Perform reformatting.

        :param data: CRIS data object
        :return: ordered list of groups containing sorted data objects
        """

        unsorted = {}

        # group data
        for _, d in data.items():
            try:
                groupvalue = (d['%s' % self.group_by]).lower()
            except KeyError:
                raise Exception('selected attribute not found: %s' % self.group_by)
            except AttributeError:
                if self.group_by is None:
                    groupvalue = self.sort_by

            if groupvalue not in unsorted.keys():
                unsorted[groupvalue] = []

            unsorted[groupvalue].append(d)

        # sort inside groups
        if self.group_order in (SORT_ASC, SORT_DESC):
            keylist = sorted(unsorted.keys(),
                             reverse=(self.group_order == SORT_DESC))
        else:
            keylist = self.group_order

            # Put missing values at the end (we have more/other values in actual
            # data than listed in group_order).
            missing = set(unsorted.keys()) - set(keylist)
            if missing:
                keylist.extend(list(missing))

        results = collections.OrderedDict()
        for k in keylist:
            # no sorting in 2nd level
            if self.sort_by is None:
                results[k] = unsorted[k]
                continue

            # skip keys that are not present in data
            if not k in unsorted:
                continue

            # sort by attribute
            try:
                _x = sorted(unsorted[k], key=lambda y: y[self.sort_by],
                        reverse=(self.sort_order == SORT_DESC))
            except TypeError:
                raise Exception('Cannot sort by unset attribute.')
            results[k] = _x

        return results


if __name__ == '__main__':
    from pprint import pprint

    p = Publications()
    result = p.by_id("1060854")
    # pprint(result)
    print(result["1060854"].toBibTeX())
    exit()

    # result = p.by_orga(142131, None, disable_orga_check=True)
    result = p.by_orga(142441, None, disable_orga_check=True)
    # pprint(result)
    for pp in result:
        try:
            result[pp].toBibTeX()
        except Exception as E:
            print(E)
            import pdb; pdb.set_trace()

    exit()

    selectors = {'publyear__gt': 2011}
    # one may init the class explicitly (otherwise this will happen implicitly)
    filt = Selector(selectors)

    # request publications of an organization
    # here: Anästhesiologische Klinik
    # one may request data from multiple organizations at once
    result = p.by_orga(141908, filt)
    print('-> unformatted result for organization')
    pprint(result)

    # just sort by updated timestamp
    f = Formatter(group_by=None, sort_by='updatedon')
    reformatted = f.execute(result)
    print('\n-> simply ordered by last update of data set (no grouping)')
    pprint(reformatted)

    # group by year and sort inside each year by publication date
    f = Formatter('publyear', SORT_ASC, 'virtualdate', SORT_DESC)
    reformatted = f.execute(result)
    print('\n-> same result, but grouped and sorted')
    pprint(reformatted)

    # fetch two distinct publication datasets
    result = p.by_id("1031963,1046308")
    print('\n-> distinct publications')
    pprint(result)

    # get publication of one (or more) persons
    result = p.by_pers((1008041, 168225), filt)
    print('\n-> publications for two people')
    pprint(result)

    # bigger example: Lehrstuhl für Methoden der empirischen Sozialforschung
    selectors = {
        # 2012-2014
        "publyear__ge": 2012,
        "publyear__lt": 2015,
        # request only publications that are created at FAU
        "FAU Publikation__eq": "yes",
    }
    # user-defined order, if data contains more values (in this example 'book')
    # it will be put at the end
    defined_order = [
        "journal article",
        "conference contribution",
        # if there's a typo...
        "it is no problem to use a value that's not present in data",
        "article in edited volumes",
    ]
    result = p.by_orga(143034, selectors)
    # defined_order is implicitly transformed to a selector instance
    f = Formatter("publication type", defined_order, "publyear", SORT_DESC)
    reformatted = f.execute(result)
    print('\n-> complex formatted for organization')
    pprint(reformatted)

    for _n, _i in result.items():
        print(_i.toBibTeX())
