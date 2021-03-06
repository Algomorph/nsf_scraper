# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: http://doc.scrapy.org/en/latest/topics/item-pipeline.html


from nsf_scraper.db.pdexcel import PandasExcelHelper
 
class FboScraperExcelPipeline(object):
     
     
    def __init__(self):
        self.db = PandasExcelHelper()
         
    def open_spider(self, spider):
        #share database with the spider
        spider.db = self.db
         
    def process_item(self, item, spider):
        self.db.add_item(item)
        return item
 
    def close_spider(self, spider):
        self.db.generate_report()
        self.db.save_all()