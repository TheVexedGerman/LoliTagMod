import praw
import prawcore
import time
import requests
import os
import re
import datetime
import json
import psycopg2
import traceback
#imports the site wrappers for the sites from the nhentai bot
import wrapper.nhentai as nhentai
import wrapper.tsumino as tsumino
import wrapper.ehentai as ehentai
import wrapper.hitomila as hitomila
import wrapper.nHentaiTagBot as bot
import postgres_credentials_modque


nhentaiKey = 0
tsuminoKey = 1
ehentaiKey = 2
hitomilaKey = 3

new_post_list = []

PARSED_SUBREDDIT = 'Animemes'
FLAIR_ID = "094ce764-898a-11e9-b1bf-0e66eeae092c"
# PARSED_SUBREDDIT = 'loli_tag_bot'

COMMENT_FOOTER = "---\n\n*I am a bot, and this action was performed automatically. Please [contact the moderators of this subreddit](https://www.reddit.com/message/compose?to=/r/Animemes) if you have any questions or concerns.*"

SPOILER_REMOVAL_COMMENT = f"""Hello Onii-Chan, your comment has been removed for containing a broken spoiler tag.

A space at the start breaks the tag on some Reddit platforms, you'll have to delete it for the tag to work properly.

For clarity:

- `>!This will work.!<`

- `>! This will not.!<`

Just edit your comment, and if it's fixed, your comment will be put back up.

Thank you for your cooperation.

{COMMENT_FOOTER}"""


SHADOWBAN_REMOVAL_COMMENT = f"""Hello Onii-Chan, your account seems to be shadowbanned.  

This was not an action taken by the /r/Animemes mods, but a site admin for something you were reported for in the past. I'd recommend going to /r/ShadowBan for more information.

{COMMENT_FOOTER}"""




def authenticate():
    print("Authenticating...")
    reddit = praw.Reddit(
        'sachimod'
        # 'lolitagmod'
        )
    print("Authenticated as {}".format(reddit.user.me()))
    reddit2 = praw.Reddit(
        'hentaimemesmod'
        )
    print("Authenticated as {}".format(reddit2.user.me()))
    return reddit, reddit2


def main():
    global reddit
    global reddit2
    reddit, reddit2 = authenticate()
    global cursor
    global db_conn
    global cursor2
    global db_conn2
    db_conn, cursor, db_conn2, cursor2 = authenticate_db()
    global watched_id_set
    watched_id_set = set()
    global watched_id_report_dict
    watched_id_report_dict = {}
    global awards_dict
    awards_dict = get_awards_dict()
    # Initialize the dictionary for spoiler comments which have been formatted incorrectly
    global spoiler_comment_dict
    spoiler_comment_dict = load_spoiler_dict()

    # run_bot()
    while True:
        run_bot()


def check_dupebro_for_redundant_info(comment):
    matches = re.findall(r'(?<=https://reddit.com/r/Animemes/comments/)[a-z0-9]{1,6}', comment.body)
    # print(comment.body)
    # print(matches)
    submission_comments = comment.submission.comments.list()
    ab_comment = None
    for com in submission_comments:
        if com.author.name == 'AnimemesBot':
            ab_comment = com
            # break
    if not ab_comment:
        return
    # print(ab_comment.body)
    ab_matches = re.findall(r'(?<=https:\/\/redd.it\/)[a-z0-9]{1,6}', ab_comment.body)
    matches = set(matches)
    try:
        matches.remove(comment.submission.id)
    except ValueError:
        pass
    print(matches)
    print(ab_matches)
    all_matches_contained = all(item in ab_matches for item in matches)
    if all_matches_contained:
        print("removeing")
        comment.mod.remove()
    return



def run_bot():
    print("Current time: " + str(datetime.datetime.now().time()))
    print("Fetching modqueue...")
    for comment in reddit.subreddit(PARSED_SUBREDDIT).mod.modqueue(only='comments', limit=None):
        print(comment.body)
        if comment.author.name == 'AnimemesBot' or comment.author.name == 'AutoModerator':
            comment.mod.approve()
            continue
        if comment.author.name == 'RepostSleuthBot':
            if "I didn't find any posts that meet the matching requirements" in comment.body:
                comment.mod.approve()
                continue
        if comment.body.lower() == 'trap' and comment.banned_by == 'AutoModerator':
            comment.mod.remove()
            continue
        has_numbers, has_redaction = check_for_violation(comment.body)
        if has_numbers:
            if not has_redaction:
                print("Approving Comment")
                comment.mod.approve()
            else:
                print("Removing Comment")
                comment.mod.remove(spam=False, mod_note='Sholi link')
        broken_spoiler = re.search(r'(?<!(`|\\))>!\s+', comment.body)
        # TODO approve comments that got edited before being processed.
        if broken_spoiler:
            reply = comment.reply(SPOILER_REMOVAL_COMMENT)
            reply.mod.distinguish(how='yes')
            comment.mod.remove(mod_note="Incorrectly formatted spoiler")
            if spoiler_comment_dict.get(comment.id):
                spoiler_comment_dict[comment.id] = datetime.datetime.now()
            else:
                spoiler_comment_dict.update({comment.id: datetime.datetime.now()})
            save_spoiler_dict(spoiler_comment_dict)
        # remove dupebro comments that contain the same posts as the animemesbot comment
        if comment.author.name == 'DupeBro':
            print('checking for similar matches with DupeBro')
            check_dupebro_for_redundant_info(comment)
        

        try:
            # shadowbanned comments appear to be removed by True, so as dumb as this check would be in a typed language
            # python checks for the existence of an object instead of just a bool.
            if comment.banned_by == True:
                try:
                    print(comment.author.id)
                except prawcore.exceptions.NotFound:
                    reply = comment.reply(SHADOWBAN_REMOVAL_COMMENT)
                    reply.mod.distinguish(how='yes')
                    comment.mod.remove(mod_note="Shadowbanned account")
        except AttributeError:
            pass


    print("Checking for improper spoilers")
    global new_post_list
    new_post_list = check_for_improper_spoilers(new_post_list)
    print("Checking for re-reported reposts")
    approve_old_reposts()
    print("Checking hentaimemes queue comments")
    for comment in reddit2.subreddit('hentaimemes').mod.modqueue(only='comments', limit=None):
        print(comment.body)
        has_numbers, has_redaction = check_for_violation(comment.body)
        if has_numbers:
            if not has_redaction:
                print("Approving Comment")
                comment.mod.approve()
            else:
                print("Removing Comment")
                comment.mod.remove(spam=False)
    
    print("Grabbing Modlog")
    grab_modlog()
    print("Banning for reposts")
    ban_for_reposts()
    print("Fetching Modmail")
    modmail_fetcher()
    print("Getting mail")
    get_mail()
    print("Updating awards")
    awards_updater()
    print("Checking for edited broken spoiler comments")
    check_for_updated_comments()
    print("Sleeping for 30 seconds...")
    time.sleep(30)


def check_for_violation(comment):
    print("checkforviolation being run")
    numbers_combi = bot.scanForURL(comment)
    improper_nhentai_numbers = check_for_improper_urls(comment)
    if numbers_combi and improper_nhentai_numbers:
        for element in improper_nhentai_numbers:
            numbers_combi[0].append(element)
    elif not numbers_combi and improper_nhentai_numbers:
        numbers_combi = [improper_nhentai_numbers, [], [], []]
    combination = []
    isRedacted = False
    if numbers_combi:
        for i, entry in enumerate(numbers_combi):
            for subentry in entry:
                combination.append([subentry, i])
        if combination:
            for entry in combination:
                number = entry[0]
                key = entry[1]
                if key == nhentaiKey:
                    processedData = nhentai.analyseNumber(number)
                elif key == tsuminoKey:
                    processedData = tsumino.analyseNumber(number)
                elif key == ehentaiKey:
                    processedData = ehentai.analyseNumber(number)
                elif key == hitomilaKey:
                    processedData = hitomila.analyseNumber(number)
                if len(processedData) > 1:
                    if processedData[-1]:
                        isRedacted = True
                        break
        return True, isRedacted
    return False, isRedacted


def get_offset(new, old):
    try:
        return new.index(old[0])
    except ValueError:
        return get_offset(new, old[1:])


def check_for_improper_spoilers(new_post_list):
    current_new_post_list = []
    ignore_list = []
    cursor.execute("SELECT id FROM sachimod_ignore_posts WHERE created_utc > %s", (datetime.datetime.now()-datetime.timedelta(days=1),))
    stored_ignore = cursor.fetchall()
    if stored_ignore:
        ignore_list = [entry[0] for entry in stored_ignore]
    for submission in reddit.subreddit(PARSED_SUBREDDIT).new(limit=100):
        # check for missing sources
        # if convert_time(submission.created_utc) < (datetime.datetime.now() - datetime.timedelta(minutes=30)):
        #     if '[multiple]' in submission.title.lower():
        #         cursor.execute("SELECT author FROM comments WHERE parent_id = %s AND author = %s", (f"t3_{submission.id}", str(submission.author)))
        #         tlc = cursor.fetchall()
        #         if len(tlc) == 0:
        #             cursor.execute("SELECT id FROM comments WHERE parent_id = %s AND author = %s", (f"t3_{submission.id}", "AutoModerator"))
        #             automod = cursor.fetchone()
        #             cursor.execute("SELECT author FROM comments WHERE parent_id = %s AND author = %s", (f"t1_{automod[0]}", str(submission.author)))
        #             op = cursor.fetchall()
        #             if len(op) == 0:
        #                 try:
        #                     mod_reports = submission.mod_reports + submission.mod_reports_dismissed
        #                 except AttributeError:
        #                     mod_reports = submission.mod_reports
        #                 if not any(mod_report[1] == "SachiMod" for mod_report in mod_reports):
        #                     if not any(mod_report[1] == "SachiMod" for mod_report in mod_reports):
        #                         submission.report('No source comment detected after 30 min.')
                

        # check for spoiler formatted title but no spoiler tag
        if '[oc]' not in submission.title.lower() and '[nsfw]' not in submission.title.lower() and '[redacted]' not in submission.title.lower() and '[' in submission.title and ']' in submission.title and not submission.spoiler and '[contest]' not in submission.title.lower():
            submission.report('Possibly missing spoiler tag')
        # check for spoiler tag byt not properly formatted title
        if submission.spoiler:
            # check title for spoiler formatting
            match = re.search(r"\[.+?\]", submission.title)
            if not match:
                if 'spoiler' in submission.title.lower():
                    try:
                        mod_reports = submission.mod_reports + submission.mod_reports_dismissed
                    except AttributeError:
                        mod_reports = submission.mod_reports
                    if not any(mod_report[1] == "SachiMod" for mod_report in mod_reports):
                        submission.report('Spoiler tagged post, improper title format')
                else:
                    print(f"Removing: {submission.title}")
                    submission.mod.remove()
                    # improperly marked spoiler flair
                    submission.flair.select(FLAIR_ID)
        # remove low resolution images

        # check for nsfw tagging
        # if submission.over_18:
        #     if '[nsfw]' not in submission.title.lower():
        #         submission.mod.remove()
        #         submission.flair.select('eeaebb92-8b38-11ea-a432-0e232b3ed13d')

        if submission.id not in ignore_list:
            try:
                if submission.preview:
                    try:
                        if submission.preview.get('images'):
                            res = submission.preview['images'][0]
                            if res['source']['height'] * res['source']['width'] < 100000:
                                submission.mod.remove()
                                submission.flair.select('c87c2ac6-1dd4-11ea-9a24-0ea0ae2c9561', text="Rule 10: Post Quality - Low Res")
                    except:
                        print(traceback.format_exc())
            except AttributeError:
                # print(traceback.format_exc())
                print(f"Post {submission.id} has no preview")
        #create a list of ids currently in new
        current_new_post_list.append(submission.id)

    # make sure there is a previous list
    print(new_post_list)
    # if new_post_list:
    #     # determine the offset between the old and the new list
    #     offset = get_offset(current_new_post_list, new_post_list)
    #     for i, entry in enumerate(new_post_list):
    #         # exit if the end of new list has been reached.
    #         if i + offset >= len(current_new_post_list):
    #             break
    #         else:
    #             # improve this so it doesn't automatically go to the next entry.
    #             # check if the ids are identical
    #             if entry != current_new_post_list[i+offset]:
    #                 print(f"{submission.id}: {submission.created_utc} was removed")
    #                 cursor.execute("UPDATE posts SET estimated_deletion_time = %s WHERE id = %s", (datetime.datetime.now(), entry))
    #                 # move the offset one back because the new list is now missing one entry.
    #                 offset += -1
    # set the new list to be the one checked next time
    return current_new_post_list
        

def check_for_improper_urls(comment):
    improper_nhentai_numbers = re.findall(r'((:?www.)?nhentai.net\/g\/.*?)(\d{1,6})', comment)
    try:
        improper_nhentai_numbers = [int(number[2]) for number in improper_nhentai_numbers]
    except ValueError:
        improper_nhentai_numbers = []
    return improper_nhentai_numbers

def authenticate_db():
    db_conn = psycopg2.connect(
    host = postgres_credentials_modque.HOST,
    database = postgres_credentials_modque.DATABASE,
    user = postgres_credentials_modque.USER,
    password = postgres_credentials_modque.PASSWORD
    )
    db_conn2 = psycopg2.connect(
    host = postgres_credentials_modque.HOST,
    database = 'hentaimemes',
    user = postgres_credentials_modque.USER,
    password = postgres_credentials_modque.PASSWORD
    )   

    return db_conn, db_conn.cursor(), db_conn2, db_conn2.cursor()


def update_db(post_id, reports_dict):
    cursor.execute("SELECT * FROM repost_report_check WHERE id = %s", [post_id])
    entry_exists = cursor.fetchone()
    if entry_exists:
        cursor.execute("UPDATE repost_report_check SET reports_json = %s, timestamp = %s WHERE id = %s", (json.dumps(reports_dict), datetime.datetime.now(), post_id))
    else:
        cursor.execute("INSERT INTO repost_report_check (id, timestamp, reports_json) VALUES (%s, %s, %s)", (post_id, datetime.datetime.now(), json.dumps(reports_dict)))
    db_conn.commit()


def make_dict(reports):
    report_dict = {}
    for report in reports:
        report_dict.update({report[0]:report[1]})
    return report_dict


def approve_old_reposts():
    for reports in reddit.subreddit(PARSED_SUBREDDIT).mod.reports(only = 'submissions'):
        if datetime.datetime.now().weekday() > 4:
            approve_weekend_reaction_meme_reposts(reports)
        approve_weekend_reaction_memes(reports)
        approve_flagged_but_now_spoiler_tagged_memes(reports)
        # Why can't I check if link flair exists without trying to get an exception?
        try:
            # check if there is a template ID (through AttributeError) and if the template ID matches the old repost one
            # if reports.link_flair_template_id == "9a07b400-3c37-11e9-a73e-0e2a828fd580":
            if "no dignity" in reports.link_flair_text.lower():
                print(reports.title)
                approve = True
                report_dict = make_dict(reports.user_reports)
                for report in reports.user_reports:
                    # if the report contains repost it can be ignored.
                    if "repost" not in report[0].lower():
                        approve = False
                        break
                if not approve and reports.id not in watched_id_set:
                    print("closer check loop")
                    cursor.execute("SELECT reports_json FROM repost_report_check WHERE id = %s", [reports.id])
                    reference_dict = cursor.fetchone()
                    # Make sure an entry exits before assignment, otherwise create empty dict
                    if reference_dict:
                        reference_dict = reference_dict[0]
                    else:
                        reference_dict = {}
                    for entry in report_dict:
                        # ignore repost reports even if they have changed number
                        if "repost" in entry.lower() and 'http' not in entry.lower():
                            continue
                        # compare the entry to the stored one if they don't match set watch and break out of loop
                        if report_dict.get(entry) != reference_dict.get(entry):
                            watched_id_set.add(reports.id)
                            watched_id_report_dict.update({reports.id:report_dict})
                            update_db(reports.id, report_dict)
                            print("No approval")
                            approve = False
                            break
                        approve = True
                # approve the post and go back to the beginning of the loop        
                if approve:
                    print("Approved")
                    reports.mod.approve()
                    update_db(reports.id, report_dict)
                    continue
        except AttributeError:
            pass
    # Check modlog for approvals of previously marked posts.
    if watched_id_set:
        for action in reddit.subreddit(PARSED_SUBREDDIT).mod.log(limit = 200):
            if action and action.target_fullname and action.target_fullname[:2] == "t3":
                if action.target_fullname[3:] in watched_id_set:
                    cursor.execute("SELECT timestamp FROM repost_report_check WHERE id = %s", [action.target_fullname[3:]])
                    time = cursor.fetchone()[0]
                    action_time = datetime.datetime.utcfromtimestamp(action.created_utc)
                    if time < action_time:
                        watched_id_set.remove(action.target_fullname[3:])
                        update_db(action.target_fullname[3:], watched_id_report_dict.pop(action.target_fullname[3:]))


def approve_flagged_but_now_spoiler_tagged_memes(reports):
    if not reports.mod_reports:
        return
    if len(reports.mod_reports) > 1:
        return
    if reports.user_reports:
        return
    if 'Possible spoiler format in title, no tagging' in reports.mod_reports[0][0]:
        print("Spoiler tag rectified")
        if reports.spoiler:
            reports.mod.approve()

def approve_weekend_reaction_meme_reposts(reports):
    if not reports.mod_reports:
        return
    if reports.user_reports:
        return
    for report in reports.mod_reports:
        print("found suspect")
        if 'Possible Repost' in report[0]:
            for comment in reports.comments.list():
                try:
                    if comment.author.name.lower() == 'animemesbot':
                        posts = re.findall(r'(?<=https:\/\/redd.it\/).{1,6}', comment.body)
                        print(posts)
                        if len(posts) == 1:
                            try:
                                if reddit.submission(id=posts[0]).link_flair_template_id == '1dda8d90-501e-11e8-98b7-0e6fcedead42':
                                    reports.mod.approve()
                            except AttributeError:
                                return
                except:
                    continue


def approve_weekend_reaction_memes(reports):
    print(reports.title)
    approve = True
    is_reaction = False
    report_dict = make_dict(reports.user_reports)
    if convert_time(reports.created_utc).weekday() < 5:
        return
    if not reports.user_reports:
        return
    for report in reports.user_reports:
        # check if reaction meme is in the report
        if report[0] and "Rule 3: Weekday Reaction Meme" not in report[0]:
            approve = False
        else:
            print("is reaction")
            is_reaction = True
    if is_reaction and not approve and reports.id not in watched_id_set:
        print("closer check loop reaction meme")
        cursor.execute("SELECT reports_json FROM repost_report_check WHERE id = %s", [reports.id])
        reference_dict = cursor.fetchone()
        # Make sure an entry exits before assignment, otherwise create empty dict
        if reference_dict:
            reference_dict = reference_dict[0]
        else:
            reference_dict = {}
        for entry in report_dict:
            if entry and "Rule 3: Weekday Reaction Meme" in entry:
                continue
            # compare the entry to the stored one if they don't match set watch and break out of loop
            if report_dict.get(entry) != reference_dict.get(entry):
                watched_id_set.add(reports.id)
                watched_id_report_dict.update({reports.id:report_dict})
                update_db(reports.id, report_dict)
                print("No approval")
                approve = False
                break
            approve = True
        # approve the post and go back to the beginning of the loop        
    if approve and is_reaction:
        reports.mod.approve()
        update_db(reports.id, report_dict)


def grab_modlog():
    for action in reddit.subreddit(PARSED_SUBREDDIT).mod.log(limit=None):
        cursor.execute("SELECT * FROM modlog WHERE id = %s", [action.id])
        exists = cursor.fetchone()
        if exists:
            break
        cursor.execute("INSERT INTO modlog (action, created_utc, description, details, id, mod, mod_id36, sr_id36, subreddit, subreddit_name_prefixed, target_author, target_body, target_fullname, target_permalink, target_title) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", (action.action, convert_time(action.created_utc), action.description, action.details, action.id, str(action.mod), action.mod_id36, action.sr_id36, action.subreddit, action.subreddit_name_prefixed, str(action.target_author), action.target_body, action.target_fullname, action.target_permalink, action.target_title))
        db_conn.commit()
    for action in reddit2.subreddit("hentaimemes").mod.log(limit=None):
        cursor2.execute("SELECT * FROM modlog WHERE id = %s", [action.id])
        exists = cursor2.fetchone()
        if exists:
            break
        cursor2.execute("INSERT INTO modlog (action, created_utc, description, details, id, mod, mod_id36, sr_id36, subreddit, subreddit_name_prefixed, target_author, target_body, target_fullname, target_permalink, target_title) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", (action.action, convert_time(action.created_utc), action.description, action.details, action.id, str(action.mod), action.mod_id36, action.sr_id36, action.subreddit, action.subreddit_name_prefixed, str(action.target_author), action.target_body, action.target_fullname, action.target_permalink, action.target_title))
        db_conn2.commit()


def convert_time(time):
    if time:
        return datetime.datetime.utcfromtimestamp(time)
    return None

def ban_for_reposts():
    # Grab flair edits from modlog
    cursor.execute("SELECT id, target_fullname FROM modlog WHERE action = 'editflair' and ban_processing = false ORDER BY created_utc DESC LIMIT 100")
    edit_flair_list = cursor.fetchall()
    check_ids = []
    # add all the fullnames into a list
    for edited_flair in edit_flair_list:
        if edited_flair[1]:
            check_ids.append(edited_flair[1])
    # Fetch them all from reddit
    if check_ids:
        for removal_suspect in reddit.info(fullnames=check_ids):
            # # check that it was posted in november
            # if convert_time(removal_suspect.created_utc) > datetime.datetime(2019, 12, 1):
            #     continue
            # check if they have the right flair
            try:
                if removal_suspect.link_flair_template_id:
                    pass
            except AttributeError:
                continue
            cursor.execute("UPDATE posts SET link_flair_template_id = %s, link_flair_text = %s WHERE id = %s", (removal_suspect.link_flair_template_id, removal_suspect.link_flair_text, removal_suspect.id))

            # Auto ban people having their posts removed again after being banned previously
            cursor.execute("SELECT created_utc, target_author FROM modlog WHERE target_author = (SELECT target_author FROM modlog WHERE target_fullname = %s AND NOT mod = 'SachiMod' LIMIT 1) AND action = 'banuser' AND created_utc > '2020-08-03' ORDER BY created_utc DESC", (removal_suspect.name,))
            previous_bans = cursor.fetchall()
            if len(previous_bans) > 0:
                ban_user(previous_bans[0][1], duration=14, note=f"Automated ban for breaking the rules after the last ban", ban_message = 'It appears you have created another rule breaking post after being banned previously. Please take some time to familiarize yourself with [our rules](https://www.reddit.com/r/Animemes/wiki/extendedrules) before posting again.', ban_reason="Automated reban")
                print(f"User: {previous_bans[0][1]} banned for the 2nd time")


        #     if removal_suspect.link_flair_template_id == 'e186588a-fcc7-11e9-8108-0e38adec5b54':
        #         # check if they have actually been removed
        #         cursor.execute("SELECT id, action, target_author FROM modlog WHERE target_fullname = %s AND NOT action = 'editflair' ORDER BY created_utc DESC", (removal_suspect.name,))
        #         current_state = cursor.fetchone()
        #         if current_state and current_state[1] == 'removelink':
        #             # ban the user
        #             cursor.execute("SELECT id, created_utc FROM modlog WHERE target_author = %s AND mod = 'SachiMod' AND action = 'banuser' ORDER BY created_utc DESC", (current_state[2],))
        #             previous_violations = cursor.fetchall()
        #             if previous_violations:
        #                 if len(previous_violations) == 1 and (datetime.datetime.now() - previous_violations[0][1] > datetime.timedelta(days=3)):
        #                     ban_user(current_state[2], duration=7, note=f"2nd automated ban for reposting a meme http://redd.it/{removal_suspect.id}", ban_message = 'Looks like the first ban did not drive the ["No Repost" part of "No Repost November"](https://www.reddit.com/r/Animemes/comments/dpwdn5/_/f5z3txs/) home. Maybe this will. See you in a week.\n\nThis is your last warning before being banned for the rest of the month. Make sure to check your post hasn\'t been posted before on Animemes. Try using the reverse image search from google and "site:reddit.com" to do so. Making OC, however, is the best way to avoid posting a repost.')
        #                     print(f"User: {current_state[2]} banned for the 2nd time")
        #                 elif len(previous_violations) == 2 and (datetime.datetime.now() - previous_violations[0][1] > datetime.timedelta(days=7)):
        #                     ban_user(current_state[2], duration=21, note=f"3rd automated ban for reposting a meme http://redd.it/{removal_suspect.id}", ban_message = 'Since the previous two bans did not manage to explain that we really mean it with ["No Reposts" during "No Repost November"](https://www.reddit.com/r/Animemes/comments/dpwdn5/_/f5z3txs/), you can just chill until December.')
        #                     print(f"User: {current_state[2]} banned for the 3rd time")
        #             else:
        #                 ban_user(current_state[2], note=f"Automated ban for reposting a meme http://redd.it/{removal_suspect.id}")
        #                 print(f"User: {current_state[2]} banned")

        # event removal processing
            if removal_suspect.link_flair_template_id == 'eeaebb92-8b38-11ea-a432-0e232b3ed13d':
                cursor.execute("SELECT id, created_utc, mod FROM modlog WHERE target_fullname = %s AND action = 'removelink' ORDER BY created_utc DESC", (removal_suspect.name,))
                log_entry = cursor.fetchone()
                if log_entry:
                    cursor.execute("INSERT INTO event_removals (id, created_utc, mod, target_id, event) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (ID) DO NOTHING", (log_entry[0], log_entry[1], log_entry[2], removal_suspect.id, "NSFW Spoiler"))
        for entry in edit_flair_list:
            cursor.execute("UPDATE modlog SET ban_processing = true WHERE id = %s", (entry[0],))
        db_conn.commit()


def ban_user(user, ban_reason = "NRN: Reposted a meme", ban_message = 'Looks like someone did not understand the ["No Repost" part of "No Repost November"](https://www.reddit.com/r/Animemes/comments/dpwdn5/_/f5z3txs/) and should have some sense [smacked into them](https://i.imgur.com/4VsscZB.png). See you in three days\n\nMake sure to check your post hasn\'t been posted before on Animemes. Try using the reverse image search from google and "site:reddit.com" to do so. Making OC, however, is the best way to avoid posting a repost.', duration = 3, note = "Automated ban for reposting a meme"):
    reddit.subreddit(PARSED_SUBREDDIT).banned.add(user, ban_reason=ban_reason, ban_message=ban_message, duration=duration, note=note)


def modmail_fetcher():
    for message in reddit.subreddit(PARSED_SUBREDDIT).mod.inbox(limit=None):
        cursor.execute("SELECT id, replies FROM modmail WHERE id = %s", [message.id])
        replies = [reply.id for reply in message.replies]
        exists = cursor.fetchone()
        if exists and exists[1] == message.replies:
            break
        cursor.execute("INSERT INTO modmail (id, created_utc, first_message_name, replies, subject, author, body, dest) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET replies = EXCLUDED.replies, dest = EXCLUDED.dest, sent_to_discord = false", (message.id, convert_time(message.created_utc), message.first_message_name, replies, message.subject, str(message.author), message.body, str(message.dest)))
        for reply in message.replies:
            cursor.execute("INSERT INTO modmail (id, created_utc, first_message_name, subject, author, parent_id, body) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING", (reply.id, convert_time(reply.created_utc), reply.first_message_name, reply.subject, str(reply.author), reply.parent_id, reply.body))
        db_conn.commit()
    for message in reddit.subreddit(PARSED_SUBREDDIT).mod.unread(limit=None):
        cursor.execute("INSERT INTO modmail (id, created_utc, subject, author, body, dest) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING", (message.id, convert_time(message.created_utc), message.subject, str(message.author), message.body, str(message.dest)))
        db_conn.commit()
        message.mark_read()


def awards_updater():
    # print(awards_dict)
    for post in reddit.subreddit(PARSED_SUBREDDIT).gilded(limit=100):
        try:
            if post.all_awardings:
                pass
        except:
            continue
        for award in post.all_awardings:
            if not check_awards_membership(award):
                cursor.execute("INSERT INTO awards (id, name) VALUES (%s, %s)", (award['id'], award['name']))
                db_conn.commit()
                awards_dict.update({award['id']: award['name']})
                sub = reddit.subreddit(PARSED_SUBREDDIT)
                stylesheet = sub.stylesheet().stylesheet
                awards_css = generate_awards_css()
                stylesheet = re.sub(r'(?<=\/\* Auto managed awards section start \*\/).*?(?=\/\* Auto managed awards section end \*\/)', awards_css, stylesheet, flags=re.DOTALL)
                sub.stylesheet.update(stylesheet, f"Automatic update to add the {award['name']} award")
    for post in reddit.subreddit(PARSED_SUBREDDIT).hot(limit=100):
        try:
            if post.all_awardings:
                pass
        except:
            continue
        for award in post.all_awardings:
            if not check_awards_membership(award):
                cursor.execute("INSERT INTO awards (id, name) VALUES (%s, %s)", (award['id'], award['name']))
                db_conn.commit()
                awards_dict.update({award['id']: award['name']})
                sub = reddit.subreddit(PARSED_SUBREDDIT)
                stylesheet = sub.stylesheet().stylesheet
                awards_css = generate_awards_css()
                stylesheet = re.sub(r'(?<=\/\* Auto managed awards section start \*\/).*?(?=\/\* Auto managed awards section end \*\/)', awards_css, stylesheet, flags=re.DOTALL)
                sub.stylesheet.update(stylesheet, f"Automatic update to add the {award['name']} award")


def check_awards_membership(award):
    # just try to see if the key is in the dict
    # for key in awards_dict.keys():
    #     if key == award['id']:
    if awards_dict.get(award['id']):
        return True
    return False


def get_awards_dict():
    dic = {}
    cursor.execute("SELECT id, name FROM awards")
    awards = cursor.fetchall()
    for award in awards:
        dic.update({award[0]: award[1]})
    return dic


def generate_awards_css():
    css_string = '\n'
    for key in awards_dict.keys():
        css_string += f'a.awarding-link[data-award-id$="{key[-6:]}"]:hover:before {{\n    content: "{awards_dict[key]}";\n}}\n'
    return css_string


def get_mail():
    for message in reddit.inbox.all(limit=None):
        cursor.execute("SELECT id, replies FROM modmail WHERE id = %s", [message.id])
        replies = [reply.id for reply in message.replies]
        exists = cursor.fetchone()
        if exists and exists[1] == message.replies:
            break
        cursor.execute("INSERT INTO sachimail (id, created_utc, first_message_name, replies, subject, author, body, was_comment, parent_id, context) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING", (message.id, convert_time(message.created_utc), message.first_message_name, replies, message.subject, str(message.author), message.body, message.was_comment, message.parent_id, message.context))
        for reply in message.replies:
            cursor.execute("INSERT INTO sachimail (id, created_utc, first_message_name, subject, author, parent_id, body, was_comment, context) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING", (reply.id, convert_time(reply.created_utc), reply.first_message_name, reply.subject, str(reply.author), reply.parent_id, reply.body, reply.was_comment, message.context))
        db_conn.commit()


def save_spoiler_dict(spoiler_dict):
    with open("spoiler_comment_dict.json", "w") as f:
        f.write(str(json.dumps(spoiler_dict, default=convert_datetime)))

def load_spoiler_dict():
    #TODO make sure the dict get's loaded with the datetime
    if not os.path.isfile("spoiler_comment_dict.json"):
        json_obj = {}
    else:
        try:
            with open("spoiler_comment_dict.json", "r") as f:
                json_obj = json.loads(f.read(), object_pairs_hook=convert_str_to_datetime)
        except json.decoder.JSONDecodeError:
            json_obj = {}
    return json_obj

def convert_datetime(date):
        return date.isoformat()

def convert_str_to_datetime(pairs):
    dic = {}
    for key, value in pairs:
        if isinstance(value, str):
            try:
                dt, _, us = value.partition(".")
                dic[key] = datetime.datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                dic[key] = value
        else:
            dic[key] = value            
    return dic

def check_for_updated_comments():
    # Check recent comments because ninja edits don't show up in the edited page.
    for comment_id in list(spoiler_comment_dict.keys()):
        if spoiler_comment_dict[comment_id] + datetime.timedelta(minutes=3) < datetime.datetime.now():
            comment = reddit.comment(id=comment_id)
            broken_spoiler = re.search(r'(?<!(`|\\))>!\s+', comment.body)
            if not broken_spoiler:
                comment.mod.approve()
                del spoiler_comment_dict[comment.id]
    # Check for older edited comments
    for comment in reddit.subreddit(PARSED_SUBREDDIT).mod.edited(only='comments', limit=100):
        if comment.id in list(spoiler_comment_dict.keys()):
            broken_spoiler = re.search(r'(?<!(`|\\))>!\s+', comment.body)
            if not broken_spoiler:
                comment.mod.approve()
                del spoiler_comment_dict[comment.id]
    # clean up old comments that are unlikely to be edited.
    for key in list(spoiler_comment_dict.keys()):
        if spoiler_comment_dict[key] < (datetime.datetime.now() - datetime.timedelta(days=1)):
            del spoiler_comment_dict[key]
    save_spoiler_dict(spoiler_comment_dict)


if __name__ == '__main__':
    while True:
        try:
            main()
        except Exception as e:
            print(traceback.format_exc())
            open("log.txt", 'a').write(f"{datetime.datetime.now().time()}:\n{traceback.format_exc()}\n")
            pass