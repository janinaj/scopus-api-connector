from lxml import etree
from datetime import datetime
from collections import defaultdict
from urllib.request import urlopen
#from rake_nltk import Rake
import os, json, time, shutil

CURRENT_YEAR = 2019

class ScopusPublication():
    @property # folder to store downloaded publication files
    def data_folder(self):
        return self.data_folder_

    @property # unique identifier of the publication (can be either DOI, Scopus ID, or PubMed ID)
    def id(self):
        return self.id_

    @property # Scopus ID (all publications have this)
    def eid(self):
        return self.eid_

    @property # DOI
    def doi(self):
        return self.doi_
    
    @property # PubMed ID
    def pmid(self):
        return self.pmid_

    @property # list of references -- to do: make into scopus_publication object
    def references(self):
        return self.references_

    @property # number of references
    def reference_count(self):
        return len(self.references_)

    @property # list of citations -- to do: make into scopus_publication object
    def citations(self):
        return self.citations_

    @property # number of downloaded citations (can be less than actual number if total citations > 5000)
    def citation_count(self):
        return len(self.citations_)

    @property
    def co_citing_eids(self):
        return self.co_citing_counts_.keys()

    @property
    def co_citing_counts(self):
        return self.co_citing_counts_

    @property
    def co_cited_eids(self):
        return self.co_cited_counts_.keys()

    @property
    def co_cited_counts(self):
        return self.co_cited_counts_

    @property # title of the publication
    def title(self):
        return self.title_

    @property # abstract of the publication
    def abstract(self):
        return self.abstract_

    @property # year published
    def pub_year(self):
        return self.pub_year_
    
    @property # journal/conference
    def pub_name(self):
        return self.pub_name_
    
    @property # ISSN of journal/conference
    def issn(self):
        return self.issn_
    
    @property
    def article_type(self):
        return self.article_type_
    
    @property
    def article_subtype(self):
        return self.article_subtype_

    @property # keywords extracted from title and abstract using RAKE (https://pypi.org/project/rake-nltk/)
    def rake_keywords(self):
        return self.rake_keywords_

    def __init__(self, data_folder, eid = None, doi = None, pmid = None, download_citations = True):
        self.API_KEY = None
        self.eid_ = None
        self.doi_ = None
        self.pmid_ = None

        if eid != None:
            self.eid_ = eid.rjust(10, '0')
            self.id_ = self.eid_
            
        if doi != None:
            self.doi_ = doi
            self.id_ = self.doi_.replace('/', '.')
           
        if pmid != None:
            self.pmid_ = pmid
            self.id_ = self.pmid_
       
        self.data_folder_ = data_folder
        self.pub_directory_ = os.path.join(data_folder, self.id_)
        self.reference_file_ = os.path.join(data_folder, self.id_, 'references.xml')
        self.citations_folder_ = os.path.join(self.pub_directory_, 'citations')
        
        self.references_ = []
        self.citations_ = None
        self.co_citing_counts_ = defaultdict(int)
        self.co_cited_counts_ = defaultdict(int)
        
        self.title_ = None
        self.abstract_ = None
        self.pub_year_ = None
        self.pub_name_ = None
        self.issn_ = None
        self.article_type_ = None
        self.article_subtype_ = None

    def set_api_key(file = None, key = None):
        if key is None and file is None:
            print('Please provide API key or path to file containing API KEY.')
        if key is not None:
            self.API_KEY = key
        else:
            if os.path.exists(file):
                with open(file, 'r') as f:
                    self.API_KEY = f.read().strip()
            else:
                print('File does not exist.')

    
    def get_publication_data(self):
        self.get_reference_file()
        self.get_eid()
        self.get_pmid()
        self.get_title()
        self.get_abstract()
        self.get_year()
        self.get_pub_name()
        self.get_issn()
        self.get_article_type()

    def get_eid(self):
        if self.reference_xml_ != None:
            eid_xml = self.reference_xml_.xpath('/ns0:abstracts-retrieval-response/ns0:coredata/ns0:eid', \
                namespaces={'ns0':'http://www.elsevier.com/xml/svapi/abstract/dtd', \
                'dc':'http://purl.org/dc/elements/1.1/'})

            if len(eid_xml) == 1:
                self.eid_ = eid_xml[0].text.replace('2-s2.0-', '')
                return eid_xml[0].text.replace('2-s2.0-', '')
            
    def get_pmid(self):
        if self.reference_xml_ != None:
            pubmed_id_xml = self.reference_xml_.xpath('/ns0:abstracts-retrieval-response/ns0:coredata/ns0:pubmed-id', \
                namespaces={'ns0':'http://www.elsevier.com/xml/svapi/abstract/dtd', \
                'dc':'http://purl.org/dc/elements/1.1/'})

            if len(pubmed_id_xml) == 1:
                self.pmid_ = pubmed_id_xml[0].text

    def get_title(self):
        self.title_ = ''
        if self.reference_xml_ != None:
            title_xml = self.reference_xml_.xpath('/ns0:abstracts-retrieval-response/ns0:coredata/dc:title', \
                namespaces={'ns0':'http://www.elsevier.com/xml/svapi/abstract/dtd', \
                'dc':'http://purl.org/dc/elements/1.1/'})

            if len(title_xml) == 1:
                self.title_ = title_xml[0].text
            elif len(title_xml) > 1:
                print('More than 1 title xml: ' + self.eid_)

    def get_abstract(self):
        self.abstract_ = ''
        if self.reference_xml_ != None:
            abstract_xmls = self.reference_xml_.xpath('/ns0:abstracts-retrieval-response' + \
                '/ns0:coredata/dc:description/abstract[@xml:lang="eng"]', \
                namespaces={'ns0':'http://www.elsevier.com/xml/svapi/abstract/dtd', \
                'dc':'http://purl.org/dc/elements/1.1/'})

            for abstract_xml in abstract_xmls:
                paragraph_xmls = abstract_xml.xpath('ns3:para', namespaces={'ns3':'http://www.elsevier.com/xml/ani/common'})
                for paragraph_xml in paragraph_xmls:
                    self.abstract_ = ' '.join([self.abstract_, paragraph_xml.xpath('string(.)')])

    def get_year(self):
        try:
            pub_date_xml = self.reference_xml_.xpath('/ns0:abstracts-retrieval-response/ns0:coredata/ns1:coverDate', \
                namespaces={'ns0':'http://www.elsevier.com/xml/svapi/abstract/dtd', \
                'ns1': 'http://prismstandard.org/namespaces/basic/2.0/'})

            self.pub_year_ = datetime.strptime(pub_date_xml[0].text, '%Y-%m-%d').year
        except Exception as e:
            pass
            
    def get_pub_name(self):
        try:
            pub_name_xml = self.reference_xml_.xpath('/ns0:abstracts-retrieval-response/ns0:coredata/ns1:publicationName', \
                namespaces={'ns0':'http://www.elsevier.com/xml/svapi/abstract/dtd', \
                'ns1': 'http://prismstandard.org/namespaces/basic/2.0/'})

            self.pub_name_ = pub_name_xml[0].text
            
        except Exception as e:
            pass
            
    def get_issn(self):
        try:
            issn_xml = self.reference_xml_.xpath('/ns0:abstracts-retrieval-response/ns0:coredata/ns1:issn', \
                namespaces={'ns0':'http://www.elsevier.com/xml/svapi/abstract/dtd', \
                'ns1': 'http://prismstandard.org/namespaces/basic/2.0/'})

            self.issn_ = issn_xml[0].text    
        except Exception as e:
            pass
            
    def get_article_type(self):
        try:
            article_type_xml = self.reference_xml_.xpath('/ns0:abstracts-retrieval-response/ns0:coredata/ns1:aggregationType', \
                namespaces={'ns0':'http://www.elsevier.com/xml/svapi/abstract/dtd', \
                'ns1': 'http://prismstandard.org/namespaces/basic/2.0/'})

            self.article_type_ = article_type_xml[0].text
        except Exception as e:
            pass
            
        try:
            article_subtype_xml = self.reference_xml_.xpath( \
                 '/ns0:abstracts-retrieval-response/ns0:coredata/ns0:subtypeDescription', \
                namespaces={'ns0':'http://www.elsevier.com/xml/svapi/abstract/dtd', \
                'ns1': 'http://prismstandard.org/namespaces/basic/2.0/'})

            self.article_subtype_ = article_subtype_xml[0].text 
        except Exception as e:
            pass
            
    def download_reference_file(self):
        if self.API_KEY is None:
            print('Please set API key using the set_api_key method.')
        else:
            try:
                if self.eid_ != None:
                    abstract_url = 'https://api.elsevier.com/content/abstract/scopus_id/{}?apiKey={}'.format(self.eid_, self.API_KEY)
                elif self.doi_ != None:
                    abstract_url = 'https://api.elsevier.com/content/abstract/doi/{}?apiKey={}'.format(self.doi_, self.API_KEY)
                elif self.pmid_ != None:
                    abstract_url = 'https://api.elsevier.com/content/abstract/pubmed_id/{}?apiKey={}'.format(self.pmid_, self.API_KEY)
                
                xml_file = urlopen(abstract_url, timeout = 1000)
                data = xml_file.read()
                xml_file.close()

                # save xml data to file
                if not os.path.exists(self.pub_directory_):
                    os.mkdir(self.pub_directory_)
                
                with open(os.path.join(self.reference_file_), 'wb') as f:
                    f.write(data)

            except Exception as e:
                print('Error getting reference file: ' + self.id_)
                print(e)
            
            time.sleep(0.25)

    def get_reference_file(self):
        if not os.path.exists(self.reference_file_):
#             print('Reference file does not exist. Please download reference file.')
            pass
        try:   
            tree = etree.parse(self.reference_file_)
            self.reference_xml_ = tree.getroot()
        except Exception as e:
            self.reference_xml_ = None

    def get_references(self):
        if self.reference_xml_ != None:
            references = self.reference_xml_.xpath('/ns0:abstracts-retrieval-response' + \
                   '/item/bibrecord/tail/bibliography/reference', \
                    namespaces={'ns0':'http://www.elsevier.com/xml/svapi/abstract/dtd'})

            for reference in references:
                title = reference.xpath('ref-info/ref-title/ref-titletext')
                ref_eid = reference.xpath('ref-info/refd-itemidlist/itemid[@idtype="SGR"]')[0].text

                if ref_eid not in self.references_:
                    if len(title) > 0:
                        self.references_.append({'eid' : ref_eid, 'title' : title[0].text})
                    else:
                        self.references_.append({'eid' : ref_eid, 'title' : None})

    def get_citations(self, reload = False):
        self.total_citations = 0

        if self.citations_ is None or reload == True:
            self.citations_ = []
            if os.path.exists(self.citations_folder_):
                for file in os.listdir(self.citations_folder_):
                    if '.json' in file:
                        with open(os.path.join(self.citations_folder_, file), 'r') as f:
                            json_data = json.load(f)

                            self.total_citations = int(json_data['search-results']['opensearch:totalResults'])

                            if 'entry' in json_data['search-results']:
                                for result in json_data['search-results']['entry']:
                                    if 'eid' in result:
                                        cit_eid = result['eid'].replace('2-s2.0-', '')
                                    else:
                                        cit_eid = None
                                        
                                    if 'prism:doi' in result:
                                        if isinstance(result['prism:doi'], (list,)):
                                            print('MULTIPLE DOIs:')
                                            print(result['prism:doi'])
                                            
                                            cit_eid = result['prism:doi'][1]['$']
                                            cit_doi = result['prism:doi'][0]['$']
                                        else:
                                            cit_doi = result['prism:doi']
                                    else:
                                        cit_doi = None
                                        
                                    try:
                                        cit_pmid = result['pubmed-id']
                                    except:
                                        cit_pmid = None

                                    if 'dc:title' in result:
                                        title = result['dc:title'].replace('<inf>', '').replace('</inf>', '') \
                                            .replace('<sup>', '').replace('</sup>', '')
                                    else:
                                        title = ''

                                    try:
                                        year = datetime.strptime(result['prism:coverDate'], '%Y-%m-%d').year
                                    except:
                                        year = None

                                    try:
                                        citation_count = int(result['citedby-count'])
                                    except:
                                        citation_count = None
                                        
                                    try:
                                        publication = result['prism:publicationName']
                                    except:
                                        publication = None
                                        
                                    try:
                                        issn = result['prism:issn']
                                    except:
                                        issn = None

                                    try:
                                        article_type = result['prism:aggregationType']
                                    except:
                                        article_type = None
                                        
                                    try:
                                        subtype = result['subtypeDescription']
                                    except:
                                        subtype = None
                                        
                                    try:
                                        countries = set()
                                        for affiliation in result['affiliation']:
                                            if 'affiliation-country' in affiliation:
                                                countries.add(affiliation['affiliation-country'])
                                            
                                        countries = list(countries)
                                        countries.sort()
                                        
                                        country = ';'.join(countries)
                                    except:
                                        country = None



                                    # make this into a ScopusPublication
                                    self.citations_.append({'eid' : cit_eid, \
                                                            'doi' : cit_doi, \
                                                            'pmid' : cit_pmid, \
                                                            'title' : title, \
                                                            'year' : year, \
                                                            'citation_count' : citation_count, \
                                                            'publication' : publication, \
                                                            'issn': issn , \
                                                            'article_type' : article_type, \
                                                            'subtype' : subtype,
                                                            'country' : country})
            else:
                self.citations_ = []

    def download_citation_files(self, by_year = False):
        try:         
            if not os.path.exists(self.citations_folder_):
                os.makedirs(self.citations_folder_)

            count_results = 0
            if not by_year:
                page_count = 0
                while True:
                    json_file = urlopen('https://api.elsevier.com/content/search/scopus?' + \
                        'query=refeid(2-s2.0-{})&apiKey={}&count=200&start={}'.format(self.eid_, self.API_KEY, page_count * 200))
                    data = json_file.read()

                    json_data = json.loads(data)
                    results = int(json_data['search-results']['opensearch:totalResults'])

                    if page_count == 0 and results > 5000:
                        print('More than 5000: ' + self.eid_)

                    if results == 0 or 'entry' not in json_data['search-results']:
                        break

                    count_results += len(json_data['search-results']['entry'])

                    #save citations to file
                    with open(os.path.join(self.citations_folder_, str(page_count) + '.json'),'wb') as f:
                        f.write(data)

                    page_count += 1

                    if page_count * 200 > results:
#                         if count_results != results:
#                             print("Woah something's wrong here: " + self.doi_)
                        break

                time.sleep(0.25)
            else:
                current_year = 2018

                year = self.pub_year_ # some publication years might be wrong
                while year <= current_year:
                    page_count = 0
                    while True:
                        json_file = urllib2.urlopen('https://api.elsevier.com/content/search/scopus?' + \
                            'query=refeid(2-s2.0-{})&apiKey={}&date={}&count=200&start={}' \
                            .format(self.eid_, self.API_KEY, year, page_count * 200))
                        data = json_file.read()

                        json_data = json.loads(data)
                        results = int(json_data['search-results']['opensearch:totalResults'])

                        if page_count == 0 and results > 5000:
                            print('More than 5000: ' + self.eid_)
                            print('Year: ' + str(year))

                        if results == 0 or 'entry' not in json_data['search-results']:
                            break

                        count_results += len(json_data['search-results']['entry'])

                        #save citations to file
                        with open(os.path.join(self.citations_folder_, str(year) + '-' + str(page_count) + '.json'),'wb') as f:
                            f.write(data)

                        page_count += 1

                        if page_count * 200 > results:
                            break

                    year += 1
                    time.sleep(0.25)

        except Exception as e:
            print('Error getting citations: ' + self.eid)
            print(e)

    def filter_citations(self, year):
        filtered_citations = []
        for citation in self.citations_:
            if citation['year'] <= year:
                filtered_citations.append(citation)

        self.citations_ = filtered_citations
        self.get_cociting_eids()


    def get_cociting_eids(self):
        for reference in self.references_:
            pub = ScopusPublication(self.data_folder_, reference['eid'])

            for citation in pub.citations:
                if citation['eid'] != self.eid_:
                    self.co_citing_counts_[citation['eid']] += 1

    def get_co_cited_eids(self):
        for citation in self.citations_:
            pub = ScopusPublication(self.data_folder_, citation['eid'])

            for reference in pub.references:
                if reference['eid'] != self.eid_:
                    self.co_cited_counts_[citation['eid']] += 1

    def get_rake_keywords(self):
        self.rake_keywords_ = []

        if not os.path.exists(self.rake_keywords_file_path_):
            text = self.title.encode('ascii', 'ignore').strip()
            text += '\n' + self.abstract.encode('ascii', 'ignore').strip()

            with open(self.rake_keywords_file_path_, 'w') as o:
                if text.strip() != '':
                    try:
                        r = Rake()
                        r.extract_keywords_from_text(text)
                        self.rake_keywords_ = r.get_ranked_phrases()
                    
                        if len(self.rake_keywords_) > 0:
                            for keyword in self.rake_keywords_:
                                o.write(keyword)
                                o.write('\n')
                    except:
                        pass
        else:
            with open(self.rake_keywords_file_path_, 'r') as f:
                for line in f:
                    self.rake_keywords_.append(line.strip())