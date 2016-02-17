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
        self.unfinished_solicitations_by_sn = {}
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
        #for list_url in list_urls[0:3]:#DEBUG_LINE
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
                #if(not self.db.contains_pims(pims_id) and not NsfSpider.got_article): #DEBUG LINE
                if(not self.db.contains_pims(pims_id)):
                    yield scrapy.Request(NsfSpider.nsf_index + link, 
                                         callback=self.parse_nsf_solicitation_page, method="GET")
                    NsfSpider.got_article = True
                else:
                    print("Document with pims_id {0:d} is already in database. SKIPPING.".format(pims_id))
        print("\n=================DONE PARSING LISTING PAGE {0:d}==============\n".format(page_id))
                    
    def try_parse_due_date(self, date_string, url, due_date_description = "full proposal due date"):
        try:
            due_date = datetime.datetime.strptime(date_string, "%B %d, %Y")
        except ValueError:
            if("Any" in date_string):
                #accepted continuously
                due_date = None
            else:
                raise RuntimeError("Could not parse "+due_date_description+" for solicitation at " 
                                   + url + ". Got string: " + date_string )
        return due_date
    
    def pregenerate_solicitation(self, title, proposal_due_date, annual, 
                              annual_text, letter_due_date):
        sol = NsfSolicitation()
        sol["title"]=title
        sol["proposal_due_date"]=proposal_due_date
        sol["check_due_date"]=False
        sol["annual"]=annual
        sol["annual_text"]=annual_text
        sol["letter_due_date"]=letter_due_date
        sol["check_letter_of_intent"]=False
        sol["filtered"]=False
        return sol
    
    def parse_nsf_solicitation_page(self, response):
        '''
        Go to the solicitation document page if one exists, build and yield
        a ready NsfSolictation otherwise. Meanwhile, get accompanying 
        information from this page.
        '''
        try:
            #sometimes, the correct, updated due date is only posted here.
            #In that case, parse it.
            has_due_date = len(response.xpath("body/table/tr/td/table/tr/td/"+
                                              "h2/text()"+
                                              "[contains(.,'DUE DATES')]")) > 0
                                              
            title = response.xpath("//span[@class='pageheadline']/text()").extract()[0]
            title = title.replace(u'\xa0',' ')
            #get rid of the extra returns/newlines and spaces in title
            title = re.sub(r'\r?\n\s*',' ',title).strip()
            annual = None
            annual_text = None
            proposal_due_date = None
            letter_due_date = None
            
            if(has_due_date):
                #make no assumptions about where the full proposal deadline is,
                #because sometimes we have letter of intent due date on the 
                #first line.
                due_date_css_classes = ["due_date_first", "due_date_indent", "due_date"]
                date_text_lines = []
                for css_class in due_date_css_classes:
                    date_text_lines += response.xpath("//p[@class='"+css_class+
                                                      "']/text()").extract()
                                                    
                stripped_lines = []
                for line in date_text_lines:
                    stripped_lines.append(line.strip())
                date_text = "\n".join(stripped_lines)
                #get rid of those pesky Unicode characters
                date_text = date_text.replace(u'\xa0',' ')
                annual_text = None
                annual = re.search(r'Annually',date_text,re.IGNORECASE) != None
                if(annual):
                    for line in stripped_lines:
                        if(re.search(r'Annually',line,re.IGNORECASE) != None):
                            annual_text = line
                            
                full_due_date_match = re.search(r"(?:Full\s*(?:Center\s*)?Proposal|Application)"+
                          "\s*(?:Deadline|Target\s*Date)[^:]*:\s*(.*)",
                          date_text, re.MULTILINE)
                if(full_due_date_match is not None):
                    full_due_date_text = full_due_date_match.group(1)
                    proposal_due_date = self.try_parse_due_date(full_due_date_text, 
                                                                response.url, "full proposal due date")
                else:
                    proposal_due_date = None
                    lines = response.xpath("body/table/tr/td/table/tr/td/h2/text()[contains(.,'DUE DATES')]/../following-sibling::p/text()").extract()[:4]
                    proposal_due_date_text = re.sub(r'\r\n\s*',' ',"\n".join(lines))
                intent_letter_match = \
                re.search(r"Letter of Intent (?:Due|Deadline) Date[^:]*:"+
                          "(?:\r?\n)?\s*(.*)", date_text, re.MULTILINE)
                if(intent_letter_match != None):
                    intent_due_date_text = intent_letter_match.group(1)
                    letter_due_date = datetime.datetime.strptime(intent_due_date_text, "%B %d, %Y")
                
            
            #scan through the links to find one leading to the correct document page
            all_links = response.xpath("body/table/tr/td/table/tr/td/p/a/@href").extract()
            #skip links in the "RELATED URLS" section
            related_links = response.xpath("body/table/tr/td/table/tr/td/p/"+
                                           "strong/text()[contains(.,'RELATED URLS')]"+
                                           "/../../a/@href").extract()
            doc_page_link = None
            for link in all_links:
                #grantsgovguide is the only external ods link we expect on these pages
                if("ods_key=" in link and "pims_id=" in link
                   and not "grantsgovguide" in link and not "ods_key=gpg" in link 
                   and not link in related_links):
                    doc_page_link = link.strip()
                    break
                
            sol = self.pregenerate_solicitation(title, proposal_due_date, annual,
                                                 annual_text, letter_due_date)
            if(has_due_date and proposal_due_date is None):
                #fill in info for manual checking
                sol["check_due_date"] = True
                sol["proposal_due_date_text"] = proposal_due_date_text
            pims_id = int(re.search(r'\d+$',response.url).group(0))
            sol["pims_id"] = pims_id
            sol["url"]=response.url
            if doc_page_link is None:
                #we failed to find a doc link, (according to Tara Burke)
                #this is not limited submission, filter it out
                sol["filtered"]=True
                yield sol
                print("======YIELDED A (FILTERED) NO-DOC SOLICITATION, PIMS {0:d}======\n".format(pims_id))
            else:
                sol_number = int(re.search(r'ods_key=nsf(\d+)',doc_page_link).group(1))
                sol["solicitation_number"] = sol_number
                
                if(self.db.contains_sol_number(sol_number) or sol_number in self.unfinished_solicitations_by_sn):
                    if(self.db.contains_sol_number(sol_number)):
                        #must have already followed that doc link in earlier sessions 
                        #or saved to the db, yield the solicitation
                        db_sol = self.db.retrieve_item_by_sol_number(sol_number)
                        #fill in the missing relevant items from the already existing data entry
                        sol["limit_per_org_text"] = db_sol["limit_per_org_text"]
                        sol["has_limit_per_org"] = db_sol["has_limit_per_org"]
                        sol["suggested_limit_per_org"] = db_sol["suggested_limit_per_org"]
                        sol["check_limit_per_org"] = db_sol["check_limit_per_org"]
                        if(not has_due_date):
                            sol["check_due_date"] = True
                            sol["check_post_date"] = True
                            sol["check_letter_of_intent"] = True
                        yield sol
                    elif(sol_number in self.unfinished_solicitations_by_sn):
                        #must have already followed that doc link in this session
                        #but not yet saved to the db, yield the solicitation
                        self.unfinished_solicitations_by_sn[sol_number].append(sol)
                else:
                    self.unfinished_solicitations_by_sn[sol_number] = [sol]
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
            doc_url = response.xpath("body/table/tr/td/table/tr/td/a[text()='TXT']/@href")[0].extract().strip()
            if "www.nsf.gov" in doc_url:
                full_doc_url = doc_url #sometimes, they have absolute links (go figure)
            else: 
                full_doc_url = NsfSpider.nsf_index + doc_url
            yield scrapy.Request(url=full_doc_url, callback=self.parse_nsf_solicitation, 
                                 method="GET")
        except:
            #if we got here, that means we could not find the proper text document URL
            try:
                sol_number = int(re.search(r'ods_key=nsf(\d+)',response.url).group(1))
                pims_id = int(re.search(r'pims_id=(\d+)',response.url).group(1))
                yielded = False
                print("\n======NO DOCUMENT FOUND FOR SOLICITATION {0:d} =====".format(sol_number))
                print("======CHECKING AGAINST LISTING-PAGE DATA & DATABASE ==".format(sol_number))
                if(sol_number in self.unfinished_solicitations_by_sn):
                    for sol in self.unfinished_solicitations_by_sn[sol_number]:
                        sol["check_limit_per_org"] = True
                        if(not "posted_date" in sol or sol["posted_date"] is None):
                            sol["check_post_date"] = True
                        if(self.db.contains_sol_number(sol_number)):
                            #fill limit from org info from database
                            db_sol = self.db.retrieve_item_by_sol_number(sol_number)
                            sol["limit_per_org_text"] = db_sol["limit_per_org_text"]
                            sol["has_limit_per_org"] = db_sol["has_limit_per_org"]
                            sol["suggested_limit_per_org"] = db_sol["suggested_limit_per_org"]
                            sol["check_limit_per_org"] = db_sol["check_limit_per_org"]
                        yield sol
                        if(sol["pims_id"] == pims_id):
                            #check if it's the same actual posting as this one
                            yielded = True
                        
                if(not yielded):
                    sol = NsfSolicitation()
                    title = response.xpath("//span[@class='pageheadline']/text()").extract()[0].strip()
                    #get rid of the extra returns and spaces in title
                    title = re.sub("\s*\n\s*|\s*\r\s*", " ", title.strip())
                    sol["pims_id"]=pims_id
                    sol["solicitation_number"]=sol_number
                    sol["title"]=title
                    sol["filtered"]=False
                    sol["url"]=response.url
                    sol["check_due_date"] = True
                    sol["check_letter_of_intent"] = True
                    sol["check_limit_per_org"] = True
                    sol["check_post_date"] = True
                    if(self.db.contains_sol_number(sol_number)):
                        #fill limit from org info & title from database
                        db_sol = self.db.retrieve_item_by_sol_number(sol_number)
                        sol["title"]=db_sol["title"]
                        sol["limit_per_org_text"] = db_sol["limit_per_org_text"]
                        sol["has_limit_per_org"] = db_sol["has_limit_per_org"]
                        sol["suggested_limit_per_org"] = db_sol["suggested_limit_per_org"]
                        sol["check_limit_per_org"] = db_sol["check_limit_per_org"]
                    yield sol
                print("\n======YIELDED AVAILABLE INFO FOR {0:d} FROM OTHER SOURCES=====".format(sol_number))
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
            
            #***************** SOLICITATION NUMBER*****************************#
            #try getting solicitation number from url first
            match_result = re.search(r"nsf(\d+).txt",response.url)
            if(match_result != None):
                solicitation_number = int(match_result.group(1))
            else:
                #solicitation code from document (sometimes they use "Announcement" instead of "Solicitation")
                solicitation_codes = re.findall(r'^(?:\[\d\])?Program (?:Solicitation|Announcement)\s+(.*)',response.body, re.MULTILINE)
                if(len(solicitation_codes) > 0):
                    solictation_code = solicitation_codes[0]
                else:
                    raise RuntimeError("Could not parse program solicitation code for " + response.url)
                num_parts = re.search(r'(\d+)\-(\d+)',solictation_code).groups()
                solicitation_number = int(num_parts[0] + num_parts[1])
            
            sol = self.unfinished_solicitations_by_sn[solicitation_number][0]
            
            #****************** POSTED DATE ***********************************#
            #assume no checks are needed initially until determined otherwise
            #date the solicitation was posted
            posted_date_strs = re.findall(r'Date?:;?\s*(.*)',response.body, re.IGNORECASE)
            #set every field to None until it's resolved
            posted_date = None
            check_post_date = False
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
            sol["check_post_date"] = check_post_date
            sol["posted_date"] = posted_date
            
            #****************** LETTER OF INTENT DUE DATE *********************#
            if(sol["letter_due_date"] is None):
                letter_due_dates = re.findall(r'Letter of Intent Due Date'+
                                              '\(s\)[^:]*:(?:\r?\n)+\s*(.*)',
                                              response.body)
                letter_due_date = None
                check_letter_of_intent = False
                if(len(letter_due_dates) > 0):
                    letter_due_date = \
                    datetime.datetime.strptime(letter_due_dates[0].strip(), 
                                               "%B %d, %Y")
                else:
                    if('Letter of Intent' in response.body or 
                       'letter of intent' in response.body):
                        check_letter_of_intent = True
                sol["letter_due_date"] = letter_due_date
                sol["check_letter_of_intent"] = check_letter_of_intent
                
            #****************** PROPOSAL DUE DATE *****************************#
            
            if(sol["proposal_due_date"] is None):
                if("Submission Window Date" in response.body):
                    #sometimes they give a window for submission instead of a single date
                    proposal_due_dates = \
                    re.findall(r'Submission Window Date\(s\)[^:]*:(?:\r?\n)+'+
                               '[^-]*-\s*(.*)',response.body)
                else:    
                    proposal_due_dates = \
                    re.findall(r'(?:Full (?:Center )?Proposal|Application)'+
                               '\s*(?:Deadline|Target Date)\(s\)[^:]*:(?:\r?\n)+\s*(.*)',response.body)
                proposal_due_date = None
                check_due_date = False
                if(len(proposal_due_dates) > 0):
                    prop_due_str = proposal_due_dates[0].strip()
                    proposal_due_date = self.try_parse_due_date(prop_due_str, 
                                                                response.url,
                                                                "full proposal due date")
                else:
                    check_due_date = True
                    #else:
                    #    raise RuntimeError("Could not find proposal deadline for solicitation " + solictation_code)
                sol["proposal_due_date"] = proposal_due_date
                sol["check_due_date"] = check_due_date
                
            #**********************ANNUAL & ANNUAL TEXT************************#
            if(sol["annual_text"] is None):
                annual = re.search(r'Annually\s*Thereafter', response.body, 
                                   re.IGNORECASE) != None
                if(annual):
                    annual_text = re.search(r'.*Annually\s*Thereafter.*', 
                                            response.body, re.IGNORECASE).group(0).strip()
                else:
                    annual_text = None
                sol["annual"] = annual
                sol["annual_text"] = annual_text
                
            #****************** LIMIT PER ORG *********************************#
            #on to get the limits on proposal numbers
            limit_on_org_sr = re.search(r'Limit on Number of Proposals per Organization[^:]*:(?:(?:\r?\n)+\s*|\s*(?=\d))',response.body)
            limit_on_PI_sr = re.search(r'Limit on Number of Proposals per PI',response.body)
            has_limit_per_org = False
            suggested_org_limit = None
            limit_org_text = None
            check_limit_per_org = False
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
            sol["limit_per_org_text"] = limit_org_text
            sol["suggested_limit_per_org"] = suggested_org_limit
            sol["has_limit_per_org"] = has_limit_per_org
            sol["check_limit_per_org"] = check_limit_per_org
            
            sol["url"] = response.url.replace(".txt",".htm")
            yield sol
            print("=======SUCCESSFULLY PARSED SOLICITATION==================\n")
            #process unfinished repostings of the same solicitation (typically, annual)
            repost_list = self.unfinished_solicitations_by_sn[solicitation_number]
            if(len(repost_list) > 1):
                repost_list = repost_list[1:]
                for repost_sol in repost_list:
                    print("=======ADDING REPLICATED SOLICIATION====================\n")
                    repost_sol["limit_per_org_text"] = limit_org_text
                    repost_sol["suggested_limit_per_org"] = suggested_org_limit
                    repost_sol["has_limit_per_org"] = has_limit_per_org
                    repost_sol["check_limit_per_org"] = check_limit_per_org
                    if(not "posted_date" in repost_sol 
                       or repost_sol["posted_date"] is None):
                        repost_sol["check_post_date"] = True
                    if(not "proposal_due_date" in repost_sol 
                       or repost_sol["proposal_due_date"] is None):
                        repost_sol["check_due_date"] = True
                    #assuming here no repost will have letter of intent
                    print("=======REPLICATED SOLICIATION ADDED=====================\n")

            #clear out the unfinished array for it
            del self.unfinished_solicitations_by_sn[solicitation_number]
            
        except:
            tb = traceback.format_exc()
            print(Fore.RED  + Style.BRIGHT + tb)#@UndefinedVariable
    
        
        
        
        
        