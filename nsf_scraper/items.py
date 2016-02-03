'''
    @author: Greg Kramida (github id: Algomorph)
 @copyright: (2015-2016) Gregory Kramida
   @license: Apache V2
            [That means (basically): feel free to modify, sell, 
             whatever, just do not remove the original author's credits/notice 
            from the files. For details, see LICENSE file.] 
'''
import scrapy

class NsfSolicitation(scrapy.Item):
    '''
    Data we need for each solicitation on the NSF website
    '''
    title = scrapy.Field(serializer=str)
    solicitation_number = scrapy.Field(serializer=int)
    pims_id = scrapy.Field(serializer=int)
    posted_date = scrapy.Field()
    letter_due_date = scrapy.Field(serializer=str)
    proposal_due_date = scrapy.Field(serializer=str)
    check_due_date = scrapy.Field(serializer=bool)
    limit_per_org_text = scrapy.Field(serializer=str)
    suggested_limit_per_org = scrapy.Field(serializer=int)
    has_limit_per_org = scrapy.Field(serializer=bool)
    check_letter_of_intent = scrapy.Field(serializer=bool)
    filtered = scrapy.Field(serializer=bool)
    url = scrapy.Field(serializer=str)
    check_limit_per_org = scrapy.Field(seializer=bool)
    check_post_date = scrapy.Field(serielizer=bool)
    
        