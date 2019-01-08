import time
import pickle

import pandas as pd

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

def create_driver(config, headless=False):
    '''Create selenium driver from the config file.  Logs the user in.'''
        
    ## Create the web driver
    if headless:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        browser = webdriver.Chrome(config['driver_path'], chrome_options=options)
    else:
        browser = webdriver.Chrome(config['driver_path'])
        
    ## Load the login url
    browser.get(UnTappdScraper.LOGIN_URL)
        
    ## Enter username and password
    for key in ['username', 'password']:
        element = browser.find_element_by_id(key)
        element.send_keys(config['login'][key])

    ## Click submit
    browser.find_element_by_xpath("//input[@type='submit']").click()
        
    ## Return our created browser element
    return browser

def create_scraper(type, browser):
    '''Creates a scraping object based on the requested input type
    input: type is expected to be a ScraperType enum
           browser is expected to be a selenium web driver
    
    '''
    if type == ScraperType.SEARCH:
        return SearchScraper(browser)
    if type == ScraperType.BEER:
        return BeerScraper(browser)
    if type == ScraperType.USER:
        return None
    
    return None


from enum import Enum
class ScraperType(Enum):
    SEARCH = 0
    BEER = 1
    USER = 2

class UnTappdScraper:
    
    LOGIN_URL = 'https://untappd.com/login'
    CHUNK_SIZE = 25
    
    def __init__(self, browser):
        self.browser = browser
        
    def load_page(self, url):
        ## Load the Page
        self.browser.get(url)
        
        ## Ensure it has an untappd element that we're expecting
        while True:
            try:
                logo = self.browser.find_element_by_class_name('logo')
                if not logo or logo.text != 'Untappd':
                    print('didnt find element.  pausing')
                    time.sleep(3)
                else:
                    break
            except:
                print('Exception caught. pausing')
                time.sleep(2)
                
        ## Try to close bottom banner if it exists
        try:
            close_me_iframe = self.browser.find_element_by_id('branch-banner-iframe')
            self.browser.switch_to.frame(close_me_iframe)
            self.browser.find_element_by_id('branch-banner-close').click()
        except:
            pass
        
        ## In case we're in the iframe, switch back to default content
        self.browser.switch_to.default_content()
        
        
    def click_show_more(self):
        ## Select show more until it doesn't show up anymore
        fail_count = 0
        
        while fail_count < 2:
            try:
                ## Grab the last one
                self.browser.find_elements_by_xpath("//*[contains(text(), 'Show More')]")[-1].click()
                time.sleep(1)

            except:
                fail_count += 1
                time.sleep(2)
        
        
class SearchScraper(UnTappdScraper):
    
    def __init__(self, browser):
        UnTappdScraper.__init__(self, browser)
        
    def scrape_search_term(self, search_term):
        url = 'https://untappd.com/search?q={}'.format(search_term.strip().replace(' ', '+'))
        self.load_page(url)
        self.click_show_more()
        
        ## Find beer links on page
        results = self.browser.find_elements_by_css_selector('.beer-item')

        urls = []
        for result in results:
            urls.extend([url.get_attribute('href') for url in result.find_elements_by_tag_name('a') if url.get_attribute('href').startswith(r'https://untappd.com/beer')])

        print(len(urls), 'beers found for search', search_term)
        return urls
        
class BeerScraper(UnTappdScraper):
    def __init__(self, browser):
        UnTappdScraper.__init__(self, browser)
        
        self.classnames = 'name,brewery,style,abv,ibu,rating,raters,date'.split(',')
        
    def _get_beer_info(self, beer_id):
        
        ## Try to click "Show More" for the beer description
        beer_descp_tag = 'beer-descrption-read-more'
        try:
            self.browser.find_element_by_class_name(beer_descp_tag).find_element_by_link_text('Show More').click()
            time.sleep(0.5) ## Pause for read more to load
            
            beer_descp_tag = 'beer-descrption-read-less'
        except:
            pass
            
        ## Populate the beer info
        beer_info = {}
        beer_info['id'] = beer_id
        
        beer_info['description'] = self.browser.find_element_by_class_name(beer_descp_tag).text[:-10]

        for classname in self.classnames:
            beer_info[classname] =  self.browser.find_element_by_class_name(classname).text
            if classname == 'name':
                beer_info[classname] = self.browser.find_element_by_class_name(classname).find_element_by_tag_name('h1').text
                
        return beer_info
        
    def _get_reviews(self, beer_id):
        ## Get reviews
        user_reviews = []

        user_reviews_elems = self.browser.find_element_by_id('main-stream').find_elements_by_class_name('checkin')
        for user_review_elem in user_reviews_elems:
            rating_dict = {}
            rating_dict['beer_id'] = beer_id
            rating_dict['user_id'] = user_review_elem.find_element_by_class_name('user').get_attribute('href')

            rating = None
            try:
                rating_spans = user_review_elem.find_element_by_class_name('rating-serving').find_elements_by_tag_name('span')
                for span in rating_spans:
                    if span.get_attribute('class').startswith('rating small'):
                        rating = span.get_attribute('class').split(' ')[-1][1:]
            except:
                pass
            
            rating_dict['rating'] = rating

            rating_dict['comment'] = None
            try:
                rating_dict['comment'] = user_review_elem.find_element_by_class_name('comment-text').text
            except:
                pass

            if rating:
                if len(rating) > 1:
                    rating = rating[0] + '.' + rating[1:]
                rating = float(rating)

            user_reviews.append(rating_dict)
            
        return user_reviews
        
    def scrape_beer(self, url):
        self.load_page(url)
        beer_id = url.split('/')[-1]
        
        beer_info = self._get_beer_info(beer_id)
        
        ## Load all possible reviews
        self.click_show_more()
        
        beer_reviews = self._get_reviews(beer_id)
        
        return beer_info, beer_reviews
        
        
def write_pkl(filename, data):
    with open(filename, 'wb') as f:
        pickle.dump(data, f)
        
def read_pkl(filename):
    with open(filename, 'rb') as f:
        return pickle.load(f)

def create_beer_df(beer_info):
    beer_df = pd.DataFrame(beer_info)
    
    beer_df['abv'] = pd.to_numeric(beer_df['abv'].str.split('%').str[0].str.replace('No ABV', ''))
    beer_df['ibu'] = pd.to_numeric(beer_df['ibu'].str.split(' ').str[0].str.replace('No', ''))

    beer_df['rating'] = pd.to_numeric(beer_df['rating'].str.replace('(', '').str.replace(')', ''))

    beer_df['date'] = pd.to_datetime(beer_df['date'].str.split(' ').str[1])

    beer_df['num ratings'] = pd.to_numeric(beer_df['raters'].str.split(' ').str[0].str.replace(',', ''))
    del beer_df['raters']

    return beer_df

def create_reviews_df(reviews):
    reviews_df = pd.DataFrame(reviews)
    reviews_df['user_id'] = reviews_df['user_id'].str.replace('https://untappd.com/user/', '')
    
    return reviews_df