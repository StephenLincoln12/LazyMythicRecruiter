import requests
from bs4 import BeautifulSoup as bs
from pprint import pprint as p
import re
import pickle
import time
import sys
import code

class Recruiter:

    def __init__(self):
        self.server = "bleeding-hollow"
        self.mythic_max = 4 # Looking for guilds under 4/8M
        self.heroic_min = 8 # Looking for guilds at 8/8H
        self.base_url = "http://www.wowprogress.com/pve/us/" # base url for WP
        self.parser = 'lxml'
        self.faction = 'horde'
        self.wcl_base_url = 'http://www.warcraftlogs.com/'
        self.wcl_key = '8b3ccebcfacb10c548b381300e5c3862' # This is a public key so no worries here

    def printProgressBar(self, iteration, total, prefix = '', suffix = '', decimals = 1, length = 100, fill = '#'):
        """
        Call in a loop to create terminal progress bar
        @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        """
        percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
        filledLength = int(length * iteration // total)
        bar = fill * filledLength + '-' * (length - filledLength)
        print '\r%s |%s| %s%% %s' % (prefix, bar, percent, suffix),
        # Print New Line on Complete
        if iteration == total:
            print("\n")


    def get_page(self, url):
        """
        Uses Requests to get contents of page
        for BS4 to read.

        Input
            url (string) - URL to perform the GET request on
        Return
            string of content from requests.get(url)
        """
        return requests.get(url).content

    def epoch_to_local(self, epoch_timestamp):
        """
        Converts epoch timestamp to localtime
        I'm currently only using this for WCL, where the epoch timestamp
        is returned with miliseconds as the last 3 digits, so I trim
        them off

        Input
            epoch_timestamp (int) - Epoch timestamp, with milliseconds
        Return
            Timestamp (string) of the epoch time 

        """
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(str(epoch_timestamp)[0:-3])))

    def get_guilds(self, save=False, load_custom=False):
        """
        Gets all guild names, rankings, and href's in WoW-Progress
        Filters based on boss kill requirements in _init

        Input
            save (string, optional) - Filename to save guild information so
                                      we dont have to grab it from WP every time
                                      Saves using Pickle
            load_custom (string, optional) - Filename of guild info to load

        Return
            self.guilds (array[dict]) - Guild information, dict has the keys
                                        guild name, progress, difficulty, href
                                        href is for WP
        """
        # Init variables
        print "Retrieving guild names and ranking from WoW-Progress..."
        self.guilds = []
        page_counter = 0 #Keeps track of what page we're on since we have to go through multiple pages
        to_break = False    # Bool to tell while loop to break or not
        first_page = True   # First page is different than the rest, so keep track of it here

        # Check to see if we want to load a custom file
        if load_custom:
            try:
                self.guilds = pickle.load(open(load_custom, 'r'))
                return True
            except:
                print "Could not load custom file {0} - parsing data from WP".format(load_custom)
        # Load data from WP
        while not to_break:
            if first_page:
                # We're on the first page, the link is a bit different
                page = bs(self.get_page(self.base_url+self.server+'/'+'?faction='+self.faction), self.parser)
                first_page = False
            else:
                try:
                    # Try to get the next page, or break if we can't AKA we hit the end
                    page = bs(self.get_page(self.base_url+self.server+'/'+'rating/next/'+str(page_counter)+'/rating./faction.'+self.faction), self.parser)
                    page_counter += 1
                except Exception as e:
                    print e
                    break
            # Get the data we want, then filter/organize it
            guild_names = [tag.nobr.string for tag in page.find_all('a', class_= re.compile('guild '+self.faction+'*'))]
            guild_rankings = page.find_all('span', class_=re.compile('innerLink ratingProgress'))
            guild_hrefs =[tag.attrs['href'] for tag in page.find_all('a', class_= re.compile('guild '+self.faction+'*'))]
            # Split rankings to get boss kills and difficulty so we can filter
            for i,rank in enumerate(guild_rankings):
                add_to_list = False
                # For some reason, WP doesnt bold heroic and normal rankings
                # So the tags are different
                try:
                    # mythic
                    rank = rank.b.string
                except:
                    # heroics/normal
                    # Also, heroics have a leading space, so strip it
                    rank = rank.string.strip()
                m = re.match(r"(?P<progress>\d{1,2})/\d{1,2} \((?P<difficulty>\w)\)", rank)
                kills = m.group('progress')
                difficulty = m.group('difficulty')

                # Filter mythic/heroic based on our variables in _init
                if difficulty == "M":
                    if int(kills) <= self.mythic_max:
                        add_to_list = True
                if difficulty == "H":
                    if int(kills) >= self.heroic_min:
                        add_to_list = True
                    else:
                        # We don't need to find anymore guilds, they are all below our min
                        to_break = True
                if add_to_list:
                    self.guilds.append({"Guild Name": guild_names[i],
                                        "Progress" : int(kills),
                                        "Difficulty": difficulty,
                                        "href" : guild_hrefs[i]})
                if to_break: break

        print("Done! Time to parse!\n\n")
        if save:
            try:
                pickle.dump(self.guilds, open(save, 'wb'))
            except Exception as e:
                print("Could not save guild information to file {0}".format(save))

    def get_guild_recent_activity(self, page):
        """
        Gets who recently left and joined guild and the date.
        Only gets first page, it goes on for quite a while and we probably dont
        care that much about more than the first page

        Input
            page (string) - BS4 page, originally from self.get_page(url)

        Return
            activity_list array(dict) - dicts contain info for who left/joined
                                        guild recently
        """
        activity_list = []
        ul = page.find_all('ul', class_='eventList')
        lis = ul[0].find_all('li', class_='event mouse_high')
        for li in lis:
            timestamp = li.find('span', class_="eventDate").string
            a = li.find('a')
            info = a.attrs['aria-label']
            character = a.string
            # Check to see if class is demon hunter, its two words instead of one
            # Thats the only class that has two words
            if 'demon hunter' in info:
                info = info.split()
                race = ' '.join(info[0:-2])
                _class = 'demon hunter'
            else:
                # For everything not a DH
                info = info.split()
                race, _class = ' '.join(info[0:-1]), info[-1]
            action = li.find('span', class_='eventHeader').text.split()[1]
            activity_list.append({'character': character,
                                  'action':    action,
                                  'race':      race,
                                  'class':     _class,
                                  'time' :    timestamp})
        return activity_list


    def get_guild_last_log(self, guild_name):
        """
        Gets the date for guild last log in WCL
        TODO - Return link for all logs in WCL. This is different than the API link
               And uses an int to ID each guild, gotta find out how to get that uid
               Also note! There is a bug if the guild in WCL has a team underneath a guild
               The guild name is incorrect, need to fix this.
        Input
            guild_name (string) - self explanatory
        Return
            start (string) - timestamp of the start time of last guild log in Uldir
        """
        page = requests.get(self.wcl_base_url+'v1/reports/guild/'+guild_name+'/'+self.server+'/us?api_key='+self.wcl_key).json()
        for log in page:
            # Zone 19 is Uldir
            if log['zone'] == 19:
                start = self.epoch_to_local(log['start'])
                return start
        return ""

    def parse_guild_info(self):
        """
        Goes through each guild in our class and parses information for each guild, including
            Recent activity (left/joined recently)
            Description
            Last Uldir Log
            Roster TODO
        """
        c = 0 # Counter for neat little progress bar
        base_url = "http://www.wowprogress.com"
        l = len(self.guilds)
        for guild in self.guilds:
            guild_name = guild["Guild Name"]
            page = bs(self.get_page(base_url+guild['href']), self.parser)
            rpw = page.find_all('div', class_="raids_week")
            description = page.find_all('div', class_="guildDescription")
            try:
                guild['description'] = description[0].string
            except:
                guild['description'] = ""
            try:
                guild['Raids per Week'] = [rpw[0].string][0][-1]
            except:
                guild['Raids per Week'] = ""
            try:
                guild['Recent Activity'] = self.get_guild_recent_activity(page)
            except:
                print guild_name
                guild['Recent Activity'] = ""
            try:
                guild['Last Log'] = self.get_guild_last_log(guild_name)
            except:
                guild['Last Log'] = ""

            self.printProgressBar(c+1, l, prefix='Progress', suffix='Guilds Complete', length=50)
            c += 1
        p(self.guilds)

# Fix epoch timestamp

if __name__ == "__main__":
    pickle_file = 'guilds.p'
    r = Recruiter()
    r.get_guilds(load_custom=pickle_file)
    r.parse_guild_info()

