import requests
from bs4 import BeautifulSoup as bs
from pprint import pprint as p
import re
import pickle
import time
import sys
import code
import xlsxwriter as xlsx

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
        self.ilvl_min = 365
        self.guilded_characters = {}
        self.guildless_characters = {}
        self.guild_blacklist = ["Roll For Fall Damage"]
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
        self.guilds = {}
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
        print "Retrieving guild names and ranking from WoW-Progress..."
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
                    else:
                        self.guild_blacklist.append(guild_names[i])
                if difficulty == "H":
                    if int(kills) >= self.heroic_min:
                        add_to_list = True
                    else:
                        # We don't need to find anymore guilds, they are all below our min
                        to_break = True
                if add_to_list:
                    self.guilds[guild_names[i]] = {"Progress" : int(kills),
                                                   "Difficulty": difficulty,
                                                   "href" : guild_hrefs[i]}
                if to_break: break

        print("Done! Time to parse!\n\n")
        if save:
            try:
                with open(save, 'wb') as f:
                    pickle.dump(self.guilds, f)
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

    def get_guild_roster(self, href, guild_name):
        """
        Gets the guild roster and info (azerite, ivl, rank, etc) from WoWProgress
        by grabbing it from the guild href+'?roster' (convenient, right?)
        Since the table in the main page is loaded via Javascript and bs cant
        grab it natively

        input
            href (string) - URL of the guild in WP
        guild_name (string) - Name of the guild (key of self.guilds dict)
        """
        url = href + '?roster'
        page = requests.get(url).content
        soup = bs(page, 'lxml')
        rows = soup.find_all('tr')
        roster = []
        for row in rows[1:]:
            d = {}
            _class = row["class"][0]
            if _class == "demon_hunter":
                _class = "demon hunter"
            cols = row.find_all('td')
            if cols:
                race = ""
                character = None
                ilvl = ""
                mplus_score = ""
                rank = ""
                href = ""
                sim_dps = ""
                for col_num, col_val in enumerate(cols):
                    if col_num == 0:
                        try:
                            rank = int(col_val.text)
                        except:
                            rank = ""
                    elif col_num == 1:
                        try:
                            race = col_val.a["aria-label"]
                            if "demon hunter" in race:
                                race = ' '.join(x for x in race.split()[0:-2])
                            else:
                                race = ' '.join(x for x in race.split()[0:-1])
                        except:
                            race = ""
                        try:
                            character = col_val.a.text
                        except:
                            character = None
                        try:
                            href = col_val.a['href']
                        except:
                            href = ""
                    elif col_num == 2:
                        try:
                            pve_score = float(col_val.text)
                        except:
                            pve_score = ""
                    elif col_num == 3:
                        ilvl = col_val.text
                        try:
                            ilvl = float(col_val.text)
                        except:
                            ilvl = ""
                    elif col_num == 4:
                        try:
                            azerite = int(col_val.span.text)
                        except:
                            azerite = ""
                    elif col_num == 5:
                        try:
                            sim_dps = float(col_val.text)
                        except:
                            sim_dps = ""
                    elif col_num == 6:
                        try:
                            mplus_score = float(col_val.text)
                        except:
                            mplus_score = ""
            if character:
                d = {'rank' : rank,
                     'ilvl': ilvl,
                     'href': href,
                     'sim_dps': sim_dps,
                     'mplus_score': mplus_score,
                     'pve_score': pve_score,
                     'race': race,
                     'class': _class,
                     'guild': guild_name}
                roster.append(character)
                self.guilded_characters[character] = d
        return roster
    def parse_guild_info(self, save=None):
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
        for guild_name in self.guilds:
            guild = self.guilds[guild_name]
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
            try:
                guild['Roster'] = self.get_guild_roster(base_url+guild['href'], guild_name)
            except Exception as e:
                print "Could not get roster for {0}: {1}".format(guild_name,e)
                guild['Roster'] = []

            self.printProgressBar(c+1, l, prefix='Progress', suffix='Guilds Complete', length=50)
            c += 1
        if save:
            try:
                with open(save, 'wb') as f:
                    pickle.dump(self.guilds, open(save, 'wb'))
            except Exception as e:
                print("Could not save guild information to file {0}: {1}".format(save, e))

    def get_characters(self):
        """
        Goes through character page for the realm and grabs characters
        If the character is already in a guild that we blacklisted or we found,
        ignore it
        Sort by ilvl, and only take up to minumum ilvl
        """
        base_url = "http://www.wowprogress.com/gearscore/us/"
        first_page = True
        page_counter = 0
        to_break = False

        while not to_break:
            if first_page == True:
                page = bs(self.get_page(base_url+self.server+'/'), self.parser)
                first_page = False
            else:
                page = bs(self.get_page(base_url+self.server+'/'+'char_rating/next/'+str(page_counter)+'#char_rating'), self.parser)
                page_counter += 1
            #print page.prettify()
            #sys.exit()
            table = page.find_all("table", {"class": "rating "})[0]
            for row in table.find_all('tr')[1:]:
                cols = row.find_all('td')
                character = cols[1].a.text
                href = cols[1].a['href']
                print href
                try:
                    guild = cols[2].a.text
                except:
                    guild = ""
                faction = cols[2].a["class"][1]
                tmp = cols[1].a["aria-label"]
                if "demon hunter" in tmp:
                    tmp = tmp.split()
                    race = tmp[0:-2]
                    _class = "demon hunter"
                else:
                    tmp = tmp.split()
                    race = ' '.join(x for x in tmp[0:-1])
                    _class = tmp[-1]
                ilvl = float(cols[4].text)
                if ilvl < self.ilvl_min:
                    to_break = True
                else:
                    if (faction == self.faction) and \
                       (guild not in self.guild_blacklist):
                        # We're good, add this guy/gal
                        try:
                            self.parse_character_info(character, href, guild, race, _class, ilvl)
                        except:
                            print href
        # Make sure everyone is parsed
        for character, d in self.guilded_characters.iterietms():
            if 'parsed' not in d.keys():
                try:
                    self.parse_character_info(character, d['href'], d['guild'], d['race'], d['class'], d['ilvl'])
                except:
                    print d['href']
        for character, d in self.guildless_characters.iteritems():
            if 'parsed' not in d.keys():
                try:
                    self.parse_character_info(character, d['href'], d['guild'], d['race'], d['class'], d['ilvl'])
                except:
                    print d['href']
    def parse_character_info(self, character, href, guild=None, race=None, _class=None, ilvl=None):
        """
        Goes to href of toon on wowprogress and parses information
        """
        # Get time and threshold
        # Threshold is to check if last logout was older than 2 weeks, dont bother
        now = int(time.time())
        time_threshold = 1209600

        base_url = 'http://www.wowprogress.com'
        page = bs(self.get_page(base_url+href), self.parser)
        armory_link = page.find('a', {"class": "armoryLink", "href": re.compile("https://worldofwarcraft.com/*")})['href']

        role_spec = page.find('td', {'style': 'font-weight:bold'}, text=re.compile("DPS*|Tank*|Healing*")).text
        spec = re.search("\(([A-Za-z ]+)\)", role_spec).group(1)
        role = role_spec.split()[0]
        tmp = page.find_all('div', {"class": "gearscore"})
        for i in tmp:
            if "Mythic+ Score BfA:" in i.text:
                try:
                    mplus_score = float(re.search(r"(\d+\.\d+)", i.text).group(1))
                except:
                    mplus_score = ""
            if "Azerite Level" in i.text:
                try:
                    azerite = int(re.search(r"(\d{1,3})", i.text).group(1))
                except Exception as e:
                    azerite = ""

        try:
            i = page.find('h2', text=re.compile(r"PvE Score*")).text
            pve_score = float(re.search(r"(\d+\.\d+)", i).group(1))
        except:
            pve_score = ""

        try:
            last_logout = page.find('div', {"class": "featured"})
            last_logout = int(last_logout.span["data-ts"])
            last_logout_ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_logout))
        except:
            last_logout = ""

        if last_logout == "":
            to_add = True
        elif last_logout != "" and (now - last_logout < time_threshold):
            to_add = True
        else:
            to_add = False

        if to_add == True:
            d = {'href': href,
                 'guild': guild,
                 'race': race,
                 'class': _class,
                 'ilvl': ilvl,
                 'role': role,
                 'spec': spec,
                 'mplus_score': mplus_score,
                 'pve_score': pve_score,
                 'azerite': azerite,
                 'last_logout': last_logout_ts,
                 'armory_link': armory_link,
                 'parsed' : 'True'
                 }
            if guild.strip() == "":
                if character not in self.guildless_characters.keys():
                    self.guildless_characters[character] = d
                else:
                    for key in d:
                        guildless_characters[character][key] = d[key]
            else:
                if character not in self.guilded_characters.keys():
                    self.guildless_characters[character] = d
                else:
                    for key in d:
                        self.guilded_characters[character][key] = d[key]

    def writer(self, filename=None):
        """Writes the excel file"""
        if not filename:
            filename = "recruitment.xlsx"
        workbook = xlsx.Workbook(filename)
        guilded_worksheet = workbook.add_worksheet("GuildedCharacters")
        nonguilded_worksheet = workbook.add_worksheet("GuildlessCharacters")
        character_headers = ['Name', 'Guild', 'Rank', 'iLvl', 'Class', 'Spec', 'Role', 'Race', 'Azerite Lvl', 'PvE Score', 'M+ Score', 'Last Logout']
        bold = workbook.add_format({'bold': True})
        # define formatting
        dk_color = workbook.add_format({'bold': True, 'font_color': '#C41F3B'})
        mage_color = workbook.add_format({'bold': True, 'font_color': '#40C7EB'})
        dh_color = workbook.add_format({'bold': True, 'font_color': '#A330C9'})
        druid_color = workbook.add_format({'bold': True, 'font_color': '#FF7D0A'})
        hunter_color = workbook.add_format({'bold': True, 'font_color': '#ABD473'})
        monk_color = workbook.add_format({'bold': True, 'font_color': '#00FF96'})
        paladin_color = workbook.add_format({'bold': True, 'font_color': '#F58CBA'})
        priest_color = workbook.add_format({'bold': True, 'font_color': 'black'})
        rogue_color = workbook.add_format({'bold': True, 'font_color': '#FFF569'})
        shaman_color = workbook.add_format({'bold': True, 'font_color': '#0070DE'})
        warlock_color = workbook.add_format({'bold': True, 'font_color': '#8787ED'})
        warrior_color = workbook.add_format({'bold': True, 'font_color': '#C79C6E'})
        
        class_colors = {'deathknight': dk_color,
                        'demon hunter': dh_color,
                        'druid' : druid_color,
                        'hunter' : hunter_color,
                        'mage': mage_color,
                        'monk': monk_color,
                        'paladin': paladin_color,
                        'priest': priest_color,
                        'rogue' : rogue_color,
                        'shaman' : shaman_color,
                        'warlock': warlock_color,
                        'warrior': warrior_color}

        guilded_worksheet.write_row(0,0,character_headers, bold)
        row = 1
        for character_name, d in self.guilded_characters.iteritems():
            col = 0
            guilded_worksheet.write_url(row, col, d['armory_link'], class_colors[d["class"]], string=character_name)
            col += 1
            a = [d["guild"], d["rank"], d['ilvl'], d["class"], d["spec"], d["role"], d["race"], d["azerite"], d["pve_score"], d["mplus_score"], d["last_logout"]]
            guilded_worksheet.write_row(row,col,a)
            row += 1

        character_headers = ['Name', 'iLvl', 'Class', 'Spec', 'Role', 'Race', 'Azerite Lvl', 'PvE Score', 'M+ Score', 'Last Logout']
        guildless_worksheet.write_row(0,0,character_headers, bold)
        for character_name, d in self.guildless_characters.iteritems():
            col = 0
            guildless_worksheet.write_url(row, col, d['armory_link'], class_colors[d["class"]], string=character_name)
            col += 1
            a = [d['ilvl'], d["class"], d["spec"], d["role"], d["race"], d["azerite"], d["pve_score"], d["mplus_score"], d["last_logout"]]
            guilded_worksheet.write_row(row,col,a)
            row += 1

        workbook.close()

if __name__ == "__main__":
    pickle_file = 'guilds.p'
    r = Recruiter()
    #r.get_guilds(save="guild.p")
    #r.parse_guild_info()
    r.get_characters()
    r.writer()
