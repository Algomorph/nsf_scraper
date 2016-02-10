'''
    @author: Greg Kramida (github id: Algomorph)
 @copyright: (2015-2016) Gregory Kramida
   @license: Apache V2
            [That means (basically): feel free to modify, sell, 
             whatever, just do not remove the original author's credits/notice 
            from the files. For details, see LICENSE file.] 
'''
import pandas as pd
from pandas.io.excel import ExcelWriter
import os
from nsf_scraper.items import NsfSolicitation
from datetime import datetime


class PandasExcelHelper(object):
    '''
    A helper class to help write notices to and read them from excel
    '''
    #how frequently to save the scraped items, i.e. interval of 5 means
    #5 items are saved at a time.
    save_interval = 1


    def __init__(self, db_filename = "nsf_solicitations.xlsx",
                 report_prefix = "report", 
                 sol_sheet_name = "solicitations",
                 filtered_sheet_name = "filtered_solicitations",
                 index_column = "pims_id"):
        '''
        Constructor
        '''
        if(not os.path.isfile(db_filename)):
            #generate a blank writable excel sheet from scratch
            field_names = [field_name for field_name in NsfSolicitation.fields]
            field_names.remove("filtered")
            writer = ExcelWriter(db_filename)
            sol_df = pd.DataFrame(columns = field_names)
            filtered_df = pd.DataFrame(columns = field_names)
            sol_df.to_excel(writer,sol_sheet_name)
            filtered_df.to_excel(writer,filtered_sheet_name)
            writer.save()
            writer.close()
        
        self.report_filename = (report_prefix + "_" 
                                + str(datetime.today())[:19]
                                .replace(":","_").replace(" ","[") + "].xlsx")

        self.db_filename = db_filename
        self.sol_sheet_name = sol_sheet_name
        self.filtered_sheet_name = filtered_sheet_name
        self.sol_df = pd.read_excel(db_filename,sol_sheet_name, index_col = index_column)
        self.filtered_df = pd.read_excel(db_filename,filtered_sheet_name, index_col = index_column)
        self.usaved_sol_counter = 0
        self.sol_counter = 0
        self.added_items = set()
        self.solicitation_numbers = set()
        for sn in self.sol_df["solicitation_number"].values:
            self.solicitation_numbers.add(sn)
        self.index_column = index_column
        
    
    def generate_report(self):
        '''
        Generates a separate excel report, consisting of non-award-type notices
        that are not yet overdue
        '''
        print "\n\n========  Generating report...  ========"
        today = datetime.today()
        df = self.sol_df.copy()
        df["new"] = pd.Series([(1 if ix in self.added_items else 0 ) 
                                      for ix in df.index ],
                                      index=df.index)
        
        report_df = df[(df["proposal_due_date"] >= today)]
        
        writer = ExcelWriter(self.report_filename)
        report_df.to_excel(writer,self.sol_sheet_name,merge_cells=False)
        writer.save()
        writer.close()
        
        print "========  Report Generated as " + self.report_filename + " ========\n"
        
        
    def add_item(self,item):
        '''
        Adds the item to the proper dataframe based on the "filtered" attribute
        [filtered == True] ==> self.filtered_df
        [filtered == False] ==> self.sol_df
        '''
        item = dict(item)
        
        filtered = item["filtered"]
        key = item[self.index_column]
        item_body = {}
        
        for field_name in item:
            if not field_name == self.index_column and not field_name == "filtered":
                item_body[field_name] = item[field_name]
                
        
        item_series = pd.Series(name=key,data=item_body)
        if(item["solicitation_number"] is not None):
            self.solicitation_numbers.add(item["solicitation_number"])
        
        if(filtered):
            self.filtered_df.loc[key] = item_series
        else:
            self.added_items.add(key)
            self.sol_df.loc[key] = item_series
            
        if(self.sol_counter < PandasExcelHelper.save_interval):
            self.sol_counter += 1
        else:
            self.sol_counter = 0
            self.save_all()
            
    def retrieve_item_by_pims(self, pims_id):
        '''
        Grab the item with the matching pims_id
        '''
        if(pims_id in self.sol_df.index):
            return self.sol_df.ix[pims_id]
        if(pims_id in self.filtered_df.index):
            return self.filtered_df[pims_id]
        return None
    
    def retrieve_item_by_sol_number(self, sol_number):
        '''
        Grab the first item you find with the matching solicitation number,
        if any
        '''
        window = self.sol_df[self.sol_df['solicitation_number']==sol_number]
        if(len(window) > 0):
            return window.iloc[0]
        else:
            return None

        
    def save_all(self):
        '''
        Dumps all solicitations in both databases to an excel file,
        into two separate spreadsheets: one for filtered items, the other
        for the remaining (relevant) items
        '''
        print "\n\n========  Saving solicitations...  ========"
        writer = ExcelWriter(self.db_filename)
        self.sol_df.to_excel(writer,self.sol_sheet_name,merge_cells=False)
        self.filtered_df.to_excel(writer,self.filtered_sheet_name,merge_cells=False)
        writer.save()
        writer.close()
        print "========  Done saving.  ========\n"
        
    def contains_pims(self,pims_id):
        '''
        Checks whether the pims_id is present in either filtered or the unfiltered dataframe
        '''
        return pims_id in self.sol_df.index or pims_id in self.filtered_df.index
    
    def contains_sol_number(self,sol_number):
        '''
        Checks whether the solicitation number is present in either filtered or the unfiltered dataframe
        '''
        return sol_number in self.solicitation_numbers