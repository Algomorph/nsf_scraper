'''
    @author: Greg Kramida (github id: Algomorph)
 @copyright: (2015-2016) Gregory Kramida
   @license: Apache V2
            [That means (basically): feel free to modify, sell, 
             whatever, just do not remove the original author's credits/notice 
            from the files. For details, see LICENSE file.] 
'''

import scrapy.http
import re
import datetime
from nsf_scraper.items import NsfSolicitation
import traceback
from colorama import Fore, Back, Style, init#@UnusedVariable

num_dict = {
    'none':0,
    'zero': 0,
    'one': 1,
    'two': 2,
    'three': 3,
    'four': 4,
    'five': 5,
    'six': 6,
    'seven': 7,
    'eight': 8,
    'nine': 9,
    'ten': 10
    }

pims_by_sn = {}
sn_by_pims = {}

class NsfSpider(scrapy.Spider):
    '''
    A utility for scraping funding solicitations off www.nsf.gov
    '''
    #spider's name (for scrapy commmand line use)
    name = "nsf"
    
    allowed_domains = ["www.nsf.gov"]
    nsf_index = "http://www.nsf.gov"
    #url to start with
    nsf_base_url = nsf_index + "/funding/funding_results.jsp"
    nsf_start_url = (nsf_index + "/funding/funding_results.jsp" +
    "?queryText=&nsfOrgs=allorg&date_slct=0&fundingType=0"+
    "&pubStatus=ACTIVE&advForm=true&Submit.x=21&Submit.y=7")


    def __init__(self, *args, **kwargs):
        '''
        Constructor
        '''
        init(autoreset=True)
        super(NsfSpider, self).__init__(*args, **kwargs)
    
    #program entry point
    def start_requests(self):
        '''    
        @override
        called to construct requests from start url(s)
        '''
        yield scrapy.Request(url = NsfSpider.nsf_start_url, 
                             callback=self.parse_initial_nsf_solicitation_list,
                             method="GET")
    
    def parse_initial_nsf_solicitation_list(self, response):
        '''
        Retrieve some meta information about the query results, i.e. how many
        solicitations are there, and start subsequent parsing of list pages
        '''           
        #get the part where it says "Showing results x through y of z"
        res_string = response.xpath("body/table/tr/td/table/tr/td/table/tr/td[@valign='top'][not(@class)]/text()")[0].extract()
        total_solicitation_count = int(re.findall(r'\d+',res_string)[2])
        #we assume here that it will remain at 20 results per page.
        #if that starts changing, then figure out how to pull this number from 
        #the first listing page.
        solicitations_per_page = 20
        list_page_count = total_solicitation_count / solicitations_per_page
        if total_solicitation_count % solicitations_per_page != 0:
            list_page_count += 1
            
        list_base_url = (NsfSpider.nsf_base_url +
                         "?fundingQueryText=&nsfOrgs=allorg&fundingType=0&pubStatus=ACTIVE&advForm=true&pg=")
        list_urls = [list_base_url + str(pagenum) for pagenum in range(1,list_page_count+1)]
        for list_url in list_urls:
        #for list_url in list_urls[0:5]:#DEBUG LINE
            yield scrapy.http.FormRequest(url=list_url,
                                          callback=self.parse_nsf_solicitation_list,
                                          method="GET")
    
    #got_article = False #DEBUG LINE
    def parse_nsf_solicitation_list(self,response):
        '''
        Parse the actual list page by generating queries that follow each
        solicitation link
        '''
        page_id = int(re.search(r'\d+$',response.url).group(0))
        print("\n=================PARSING LISTING PAGE {0:d}===================\n".format(page_id))
        sol_a_tags = response.xpath("body/table/tr/td/table/tr/td/table/tr/td[@class='tabletext2']/a")
        sol_links = sol_a_tags.xpath("@href").extract()
        for link in sol_links:
            pims_id = int(re.search(r'\d+$',link).group(0))
            if(pims_id > 0):
                #if(not self.db.contains(pims_id) and not NsfSpider.got_article): #DEBUG LINE
                if(not self.db.contains(pims_id)):
                    yield scrapy.Request(NsfSpider.nsf_index + link, 
                                         callback=self.parse_nsf_solicitation_page, method="GET")
                    NsfSpider.got_article = True
                else:
                    print("Document with pims_id {0:d} is already in database. SKIPPING.".format(pims_id))
    
    def parse_nsf_solicitation_page(self, response):
        '''
        All we need to do here is go to the solicitation document page
        '''
        try:
            all_links = response.xpath("body/table/tr/td/table/tr/td/p/a/@href").extract()
            doc_page_link = None
            for link in all_links:
                #grantsgovguide is the only external ods link we expect on these pages
                if "ods_key=" in link and "pims_id=" in link and not "grantsgovguide" in link:
                    doc_page_link = link.strip()
                    break
            if doc_page_link is None:
                #we failed to find a doc link, this is not limited submission, filter it out
                sol = NsfSolicitation()
                title = response.xpath("//span[@class='pageheadline']/text()")[0].extract().strip()
                #get rid of the extra returns and spaces in title
                title = re.sub("\s*\n\s*|\s*\r\s*", " ", title.strip())
                sol["pims_id"]=int(re.search(r'\d+$',response.url).group(0))
                sol["title"]=title
                sol["filtered"]=True
                sol["url"]=response.url
                yield sol
            else:            
                pims_id = int(re.search(r'pims_id=(\d+)',doc_page_link).group(1))
                sol_number = int(re.search(r'ods_key=nsf(\d+)',doc_page_link).group(1))
                sn_by_pims[pims_id] = sol_number
                pims_by_sn[sol_number] = pims_id
                
                yield scrapy.Request(NsfSpider.nsf_index + doc_page_link, 
                                     callback=self.parse_nsf_publication_page, method="GET")
        except:
            tb = traceback.format_exc()
            print(Fore.RED  + Style.BRIGHT + tb)#@UndefinedVariable

    def parse_nsf_publication_page(self, response):
        '''
        All we need to do this is open the HTML version of the publication
        '''
        try:
            doc_url = response.xpath("body/table/tr/td/table/tr/td/a[text()='TXT']/@href")[0].extract()
            yield scrapy.Request(url=NsfSpider.nsf_index + doc_url, callback=self.parse_nsf_solicitation, 
                                 method="GET")
        except:
            try:
                sol = NsfSolicitation()
                title = response.xpath("//span[@class='pageheadline']/text()").extract()[0].strip()
                #get rid of the extra returns and spaces in title
                title = re.sub("\s*\n\s*|\s*\r\s*", " ", title.strip())
                sol["pims_id"]=int(re.search(r'pims_id=(\d+)',response.url).group(1))
                sol["solicitation_number"]=int(re.search(r'ods_key=nsf(\d+)',response.url).group(1))
                sol["title"]=title
                sol["filtered"]=False
                sol["url"]=response.url
                sol["check_due_date"] = True
                sol["check_letter_of_intent"] = True
                sol["check_limit_per_org"] = True
                sol["check_post_date"] = True
            except:
                tb = traceback.format_exc()
                print(Fore.RED  + Style.BRIGHT + tb)#@UndefinedVariable
    
    def parse_nsf_solicitation(self, response):
        '''
        All we need here is to get to the HTML representation of the published 
        solicitation
        '''
        try:
            print("\n=======ATTEMPTING TO PARSE SOLICITATION==================")
            #assume no checks are needed initially until determined otherwise
            check_due_date = False
            check_letter_of_intent = False
            check_limit_per_org = False
            check_post_date = False
            #date the solicitation was posted
            posted_date_strs = re.findall(r'Date?:;?\s*(.*)',response.body, re.IGNORECASE)
            #set every field to None until it's resolved
            posted_date = None
            if(len(posted_date_strs) == 0):
                check_post_date = True
            else:
                posted_date_str = posted_date_strs[0].strip()
                try:
                    posted_date = datetime.datetime.strptime(posted_date_str,"%m/%d/%Y")
                except ValueError:
                    try:
                    #sometimes, they use a two-digit year instead of a four-digit one
                        posted_date = datetime.datetime.strptime(posted_date_str,"%m/%d/%y")
                    except ValueError:
                        check_post_date = True
                
            expanded_title = re.findall(r'Title:\s*([^\n]*\n.*)',response.body, re.IGNORECASE)[0]
            
            #solicitation code (sometimes they use "Announcement" instead of "Solicitation")
            solicitation_codes = re.findall(r'^(?:\[\d\])?Program (?:Solicitation|Announcement)\s+(.*)',response.body, re.MULTILINE)
            if(len(solicitation_codes) > 0):
                solictation_code = solicitation_codes[0]
            else:
                raise RuntimeError("Could not parse program solicitation code for " + response.url)
            num_parts = re.search(r'(\d+)\-(\d+)',solictation_code).groups()
            solicitation_number = int(num_parts[0] + num_parts[1])
            #that gave us hint at which point the title needs to be truncated
            title = re.sub("\s*\n\s*|\s*\r\s*", " ", 
                           expanded_title[0:expanded_title
                                          .find("(nsf"+str(solicitation_number)+")")]
                           .strip())
            
            pims_id = pims_by_sn[solicitation_number]
            
            letter_due_dates = re.findall(r'Letter of Intent Due Date\(s\)[^:]*:(?:\r?\n)+\s*(.*)',response.body)
            letter_due_date = None
            if(len(letter_due_dates) > 0):
                letter_due_date = datetime.datetime.strptime(letter_due_dates[0].strip(), "%B %d, %Y")
            else:
                if('Letter of Intent Due' in response.body or 'letter of intent due' in response.body):
                    check_letter_of_intent = True
                
            
            if("Submission Window Date" in response.body):
                #sometimes they give a window for submission instead of a single date
                proposal_due_dates = re.findall(r'Submission Window Date\(s\)[^:]*:(?:\r?\n)+[^-]*-\s*(.*)',response.body)
            else:    
                proposal_due_dates = re.findall(r'(?:Full (?:Center )?Proposal|Application)\s*Deadline\(s\)[^:]*:(?:\r?\n)+\s*(.*)',response.body)
            
            proposal_due_date = None
            if(len(proposal_due_dates) > 0):
                prop_due_str = proposal_due_dates[0].strip()
                try:
                    proposal_due_date = datetime.datetime.strptime(prop_due_str, "%B %d, %Y")
                except ValueError:
                    if("Any" in prop_due_str):
                        #accepted continuously
                        proposal_due_date = None
                    else:
                        raise RuntimeError("Could not parse proposal deadline for solicitation " 
                                           + solictation_code + ". Got string: " + proposal_due_date )
            else:
                if("Full Proposal Target Date" in response.body):
                    check_due_date = True
                    proposal_due_date = None
                else:
                    raise RuntimeError("Could not find proposal deadline for solicitation " + solictation_code)
            
            #on to get the limits on proposal numbers
            limit_on_org_sr = re.search(r'Limit on Number of Proposals per Organization[^:]*:(?:(?:\r?\n)+\s*|\s*(?=\d))',response.body)
            limit_on_PI_sr = re.search(r'Limit on Number of Proposals per PI',response.body)
            has_limit_per_org = False
            suggested_org_limit = None
            limit_org_text = None
            if(limit_on_org_sr is None or limit_on_PI_sr is None):
                check_limit_per_org = True
            else:
                limit_org_text = re.sub('\n\n?\s*', " ", response.body[limit_on_org_sr.end():limit_on_PI_sr.start()])
                limit_re = re.compile("none|one|two|three|four|five|six|seven|eight|nine|ten|[0-9]|10", re.IGNORECASE)
                sr = re.search(limit_re, limit_org_text)
                suggested_org_limit = None
                has_limit_per_org = True 
                if(sr is not None):
                    #if search yielded a result, suggest this number
                    limit_org_str = sr.group(0).lower()
                    try:
                        suggested_org_limit = int(limit_org_str)
                    except ValueError:
                        suggested_org_limit = num_dict[limit_org_str]
                    if suggested_org_limit == 0:
                        suggested_org_limit = None
                else:
                    has_limit_per_org = False
                
            
            sol = NsfSolicitation()
            sol["title"] = title
            sol["solicitation_number"] = solicitation_number
            sol["pims_id"] = pims_id
            sol["posted_date"] = posted_date
            sol["letter_due_date"] = letter_due_date
            sol["proposal_due_date"] = proposal_due_date
            sol["limit_per_org_text"] = limit_org_text
            sol["suggested_limit_per_org"] = suggested_org_limit
            sol["has_limit_per_org"] = has_limit_per_org
            sol["filtered"] = False
            sol["url"] = response.url.replace(".txt",".htm")
            sol["check_due_date"] = check_due_date
            sol["check_letter_of_intent"] = check_letter_of_intent
            sol["check_limit_per_org"] = check_limit_per_org
            sol["check_post_date"] = check_post_date
            print("=======SUCCESSFULLY PARSED SOLICITATION==================\n")
            
            yield sol
        except:
            tb = traceback.format_exc()
            print(Fore.RED  + Style.BRIGHT + tb)#@UndefinedVariable
    
        
        
        
        
        