import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

def create_browser(config):
    '''Create selenium driver from the config file.  Logs the user in.'''
        
    ## Create the web driver, and load the login URL
    browser = webdriver.Chrome(config['driver_path'])
    browser.get(UnTappdScraper.LOGIN_URL)
        
    ## Enter username and password
    for key in ['username', 'password']:
        element = browser.find_element_by_id(key)
        element.send_keys(config[key])

    ## Click submit
    browser.find_element_by_xpath("//input[@type='submit']").click()
        
    ## Return our created browser element
    return browser

def create_search_scraper(browser):
    '''Creates a search scraping object'''
    return SearchScraper(browser)

def create_beer_scraper(browser):
    '''Creates a beer page scraper'''
    return BeerScraper(browser)

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
        try:
            self.browser.find_element_by_class_name('beer-descrption-read-more').find_element_by_link_text('Show More').click()
            time.sleep(0.5) ## Pause for read more to load
        except:
            print('No "Read More" in beer description for url', url)
            
        ## Populate the beer info
        beer_info = {}
        beer_info['id'] = beer_id
        
        beer_info['description'] = self.browser.find_element_by_class_name('beer-descrption-read-less').text[:-10]

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

            try:
                rating = None
                rating_spans = user_review_elem.find_element_by_class_name('rating-serving').find_elements_by_tag_name('span')
                for span in rating_spans:
                    if span.get_attribute('class').startswith('rating small'):
                        rating = span.get_attribute('class').split(' ')[-1][1:]
            except:
                continue

            rating_dict['comment'] = None
            try:
                rating_dict['comment'] = user_review_elem.find_element_by_class_name('comment-text').text
            except:
                pass

            if rating:
                if len(rating) > 1:
                    rating = rating[0] + '.' + rating[1:]
                rating = float(rating)

            rating_dict['rating'] = rating

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
        
        
        