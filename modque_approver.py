import praw
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


PARSED_SUBREDDIT = 'Animemes'
FLAIR_ID = "094ce764-898a-11e9-b1bf-0e66eeae092c"
# PARSED_SUBREDDIT = 'loli_tag_bot'

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
    db_conn, cursor = authenticate_db()
    global watched_id_set
    watched_id_set = set()
    global watched_id_report_dict
    watched_id_report_dict = {}
    # run_bot()
    while True:
        run_bot()


def run_bot():
    print("Current time: " + str(datetime.datetime.now().time()))
    print("Fetching modqueue...")
    for comment in reddit.subreddit(PARSED_SUBREDDIT).mod.modqueue(only='comments', limit=None):
        if comment.author.name == 'AnimemesBot':
            comment.mod.approve()
            continue
        print(comment.body)
        has_numbers, has_redaction = check_for_violation(comment.body)
        if has_numbers:
            if not has_redaction:
                print("Approving Comment")
                comment.mod.approve()
            else:
                print("Removing Comment")
                comment.mod.remove(spam=False)
    print("Checking for improper spoilers")
    check_for_improper_spoilers()
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


def check_for_improper_spoilers():
    for submission in reddit.subreddit(PARSED_SUBREDDIT).new(limit=100):
        # check for spoiler formatted title but no spoiler tag
        if '[oc]' not in submission.title.lower() and '[nsfw]' not in submission.title.lower() and '[' in submission.title and ']' in submission.title and not submission.spoiler:
            submission.report('Possible spoiler format in title, no tagging')
        # check for spoiler tag byt not properly formatted title
        if submission.spoiler:
            # check title for spoiler formatting
            match = re.search(r"\[.+?\]", submission.title)
            if not match:
                print(f"Removeing: {submission.title}")
                submission.mod.remove()
                # improperly marked spoiler flair
                submission.flair.select(FLAIR_ID)

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

    return db_conn, db_conn.cursor()


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
        # Why can't I check if link flair exists without trying to get an exception?
        try:
            # check if there is a template ID (through AttributeError) and if the template ID matches the old repost one
            if reports.link_flair_template_id == "9a07b400-3c37-11e9-a73e-0e2a828fd580":
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


def approve_weekend_reaction_meme_reposts(reports):
    if not reports.mod_reports:
        return
    if reports.user_reports:
        return
    for report in reports.mod_reports:
        print("found suspect")
        if 'Possible Repost: check comments' in report[0]:
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
    for action in reddit.subreddit("animemes").mod.log(limit=None):
        cursor.execute("SELECT * FROM modlog WHERE id = %s", [action.id])
        exists = cursor.fetchone()
        if exists:
            break
        cursor.execute("INSERT INTO modlog (action, created_utc, description, details, id, mod, mod_id36, sr_id36, subreddit, subreddit_name_prefixed, target_author, target_body, target_fullname, target_permalink, target_title) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", (action.action, convert_time(action.created_utc), action.description, action.details, action.id, str(action.mod), action.mod_id36, action.sr_id36, action.subreddit, action.subreddit_name_prefixed, str(action.target_author), action.target_body, action.target_fullname, action.target_permalink, action.target_title))
        db_conn.commit()


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
            # check if they have the right flair
            try:
                if removal_suspect.link_flair_template_id:
                    pass
            except AttributeError:
                continue
            if removal_suspect.link_flair_template_id == 'e186588a-fcc7-11e9-8108-0e38adec5b54':
                # check if they have actually been removed
                cursor.execute("SELECT id, action, target_author FROM modlog WHERE target_fullname = %s AND NOT action = 'editflair' ORDER BY created_utc DESC", (removal_suspect.name,))
                current_state = cursor.fetchone()
                if current_state and current_state[1] == 'removelink':
                    # ban the user
                    cursor.execute("SELECT id, created_utc FROM modlog WHERE target_author = %s AND mod = 'SachiMod' AND action = 'banuser' ORDER BY created_utc DESC", (current_state[2],))
                    previous_violations = cursor.fetchall()
                    if previous_violations:
                        if len(previous_violations) == 1 and (datetime.datetime.now() - previous_violations[0][1] > datetime.timedelta(days=3)):
                            ban_user(current_state[2], duration=7, note=f"2nd automated ban for reposting a meme http://redd.it/{removal_suspect.id}", ban_message = 'Looks like the first ban did not drive the ["No Repost" part of "No Repost November"](https://www.reddit.com/r/Animemes/comments/dpwdn5/_/f5z3txs/) home. Maybe this will. See you in a week.\n\nThis is your last warning before being banned for the rest of the month. Make sure to check your post hasn\'t been posted before on Animemes. Try using the reverse image search from google and "site:reddit.com" to do so. Making OC, however, is the best way to avoid posting a repost.')
                            print(f"User: {current_state[2]} banned for the 2nd time")
                        elif len(previous_violations) == 2 and (datetime.datetime.now() - previous_violations[0][1] > datetime.timedelta(days=7)):
                            ban_user(current_state[2], duration=21, note=f"3rd automated ban for reposting a meme http://redd.it/{removal_suspect.id}", ban_message = 'Since the previous two bans did not manage to explain that we really mean it with ["No Reposts" during "No Repost November"](https://www.reddit.com/r/Animemes/comments/dpwdn5/_/f5z3txs/), you can just chill until December.')
                            print(f"User: {current_state[2]} banned for the 3rd time")
                    else:
                        ban_user(current_state[2], note=f"Automated ban for reposting a meme http://redd.it/{removal_suspect.id}")
                        print(f"User: {current_state[2]} banned")
            elif removal_suspect.link_flair_template_id == '971f97d6-0553-11ea-b4c7-0e2542370189':
                cursor.execute("SELECT mod FROM modlog WHERE target_fullname = %s AND action = 'editflair' ORDER BY created_utc DESC", (removal_suspect.name,))
                mod = cursor.fetchone()
                cursor.execute("SELECT * FROM saves WHERE mod = %s", (mod[0],))
                entry_exists = cursor.fetchone()
                if entry_exists:
                    counter = 0
                    for entry in entry_exists[2:]:
                        if entry != None:
                            counter += 1
                    if counter > 5:
                        continue
                    # totally not sanitzed, but I don't actually expect any SQL injection from the data input
                    cursor.execute(f"UPDATE saves SET id_{counter} = '{removal_suspect.id}' WHERE mod = '{mod[0]}'")
                else:
                    cursor.execute("INSERT INTO saves (mod, id_0) VALUES (%s, %s)", (mod[0], removal_suspect.id))
            elif removal_suspect.link_flair_template_id == '21e8170e-04fe-11ea-944d-0ee316f9f307':
                cursor.execute("SELECT id, created_utc, mod FROM modlog WHERE target_fullname = %s AND action = 'removelink' ORDER BY created_utc DESC", (removal_suspect.name,))
                log_entry = cursor.fetchone()
                if log_entry:
                    cursor.execute("INSERT INTO event_removals (id, created_utc, mod, target_id) VALUES (%s, %s, %s, %s)", (log_entry[0], log_entry[1], log_entry[2], removal_suspect.id))
        for entry in edit_flair_list:
            cursor.execute("UPDATE modlog SET ban_processing = true WHERE id = %s", (entry[0],))
        db_conn.commit()


def ban_user(user, ban_reason = "NRN: Reposted a meme", ban_message = 'Looks like someone did not understand the ["No Repost" part of "No Repost November"](https://www.reddit.com/r/Animemes/comments/dpwdn5/_/f5z3txs/) and should have some sense [smacked into them](https://i.imgur.com/4VsscZB.png). See you in three days\n\nMake sure to check your post hasn\'t been posted before on Animemes. Try using the reverse image search from google and "site:reddit.com" to do so. Making OC, however, is the best way to avoid posting a repost.', duration = 3, note = "Automated ban for reposting a meme"):
    reddit.subreddit('animemes').banned.add(user, ban_reason=ban_reason, ban_message=ban_message, duration=duration, note=note)

if __name__ == '__main__':
    while True:
        try:
            main()
        except Exception as e:
            print(traceback.format_exc())
            open("log.txt", 'a').write(f"{datetime.datetime.now().time()}:\n{traceback.format_exc()}\n")
            pass