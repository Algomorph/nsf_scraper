# -*- coding: utf-8 -*-
#from scrapy.settings.default_settings import DOWNLOAD_DELAY
#from scrapy.settings.default_settings import ITEM_PIPELINES

# Scrapy settings for fbo_scraper project
#
# For simplicity, this file contains only the most important settings by
# default. All the other settings are documented here:
#
#     http://doc.scrapy.org/en/latest/topics/settings.html
#

BOT_NAME = 'nsf_scraper'

SPIDER_MODULES = ['nsf_scraper.spiders']
ITEM_PIPELINES = {'nsf_scraper.pipelines.FboScraperExcelPipeline':0}
NEWSPIDER_MODULE = 'nsf_scraper.spiders'

ROBOTSTXT_OBEY = False
RANDOMIZE_DOWNLOAD_DELAY = True
DOWNLOAD_DELAY = 5.0
DUPEFILTER_DEBUG = True

# Crawl responsibly by identifying yourself (and your website) on the user-agent
# !!! ATTENTION: PLEASE REPLACE WITH YOUR OWN WEBSITE IF YOU ARE GOING TO USE USER_AGENT!
USER_AGENT = 'nsf_scraper (+http://research.umd.edu/)'
