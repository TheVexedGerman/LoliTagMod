import praw
import prawcore
import time
import requests
import os
import re
import datetime
import json
import psycopg2
import psycopg2.errors
import traceback
#imports the site wrappers for the sites from the nhentai bot
from wrapper.nhentai import Nhentai
from wrapper.ehentai import Ehentai
from wrapper.tsumino import Tsumino
# import wrapper.hitomila as hitomila

from wrapper.DBConn import Database
from wrapper.nHentaiTagBot import NHentaiTagBot as TagBot
import postgres_credentials_modque


nhentaiKey = 0
tsuminoKey = 1
ehentaiKey = 2
hitomilaKey = 3

new_post_list = []

PARSED_SUBREDDIT = 'Animemes'
# FLAIR_ID = "094ce764-898a-11e9-b1bf-0e66eeae092c"
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


common_phrases_list = [
    "sauce?",
    "u/savethisvideo",
    "a",
    "same",
    "yes",
    "sauce",
    "u/vredditdownloader",
    "thanks",
    "u/repostsleuthbot",
    "no",
    "f",
    "nice",
    "what the fuck",
    "repost",
    "lol",
    "thank you",
    "bruh",
    "happy cake day",
    "ok",
    "true",
    "lmao",
    "?",
    "oh no",
    "thx",
    "yeah",
    "good bot",
    "{attack on titan}",
    "b",
    "yes.",
    "happy cake day!",
    "indeed",
    "noice",
    "what",
    "relatable",
    "thanks!",
    "thank you!",
    "agreed",
    "anime?",
    "always has been",
    "genshin impact",
    "what anime is this?",
    "yep",
    "exactly",
    "wtf",
    "konosuba",
    "why?",
    "based",
    "do",
    "me too",
    "sauce ?",
    "so true",
    "thank you jesus",
    "go to horny jail",
    "smol echidna",
    "what?",
    "emergency food",
    "oh",
    "oof",
    "sause",
    "simp",
    "why",
    ".",
    "hmm",
    "mood",
    "no u",
    "r/holup",
    "sauce pls",
    "even better",
    "facts",
    "fire force",
    "g",
    "gabriel dropout",
    "me",
    "no.",
    "overflow",
    "sauce please",
    "what anime is this",
    "177013",
    "bonk",
    "cringe",
    "hi",
    "hol up",
    "k",
    "pog",
    "r/cursedcomments",
    "same here",
    "test",
    "thank you.",
    ":(",
    "a.",
    "fuck",
    "goblin slayer",
    "good",
    "hehe",
    "ikr",
    "latom",
    "r/repostsleuthbot",
    "source?",
    "x",
    "yea",
    "y e s",
    "yup",
    "あ",
    "both is good",
    "e",
    "fate",
    "i agree",
    "n",
    "r/hornyjail",
    "sause?",
    "thanks man",
    "very noice",
    "wait what",
    "weak",
    "weathering with you",
    "wha",
    "xd",
    "yes it is",
    "326395",
    "amen",
    "ara ara",
    "bad bot",
    "damn",
    "hell yeah",
    "i don't know enough to answer you yet!",
    "i know",
    "is it good?",
    "rip",
    "stop",
    "this",
    "what anime is this from?",
    "😂",
    "charlotte",
    "fair enough",
    "fbi open up",
    "good question",
    "h",
    "holy shit",
    "is it possible to learn this power?",
    "maybe",
    "nisekoi",
    "not my proudest fap",
    "rent a girlfriend",
    "re zero",
    "sauces?",
    "t",
    "u/repostsleuthbot watch",
    "what anime is that?",
    "who?",
    "why must you hurt me in this way",
    "why not both?",
    "amazing",
    "angel beats",
    "another",
    "birdy the mighty",
    "black clover",
    "darling in the franxx",
    "good meme",
    "both, both is good",
    "f, same",
    """{attack on titan}

u/roboragi""",
    "r/egg_irl",
    "worth it",
    "waifu",
    "uwu",
    "...",
    "both, both is good.",
    "lmfao",
    "u/savevideo",
    "just monika",
    "bro",
    "🥒",
    "#a",
    "# a",
    "bro...",
    "gawr gura",
    "this is the way",
    "yankee jk kuzuhana-chan",
    "fax",
    "this is... the power of ^(*a jojo part 5 spoiler*) >![requiem](https://youtu.be/qs3t2pe4zse?t=122)!<."
]

def authenticate():
    print("Authenticating...")
    reddit = praw.Reddit(
        'sachimod'
        # 'lolitagmod'
        )
    print("Authenticated as {}".format(reddit.user.me()))
    return reddit


def main():
    reddit = authenticate()
    db_conn, cursor = authenticate_db()
    global watched_id_set
    watched_id_set = set()
    global watched_id_report_dict
    watched_id_report_dict = {}
    global awards_dict
    awards_dict = get_awards_dict(cursor)
    # Initialize the dictionary for spoiler comments which have been formatted incorrectly
    global spoiler_comment_dict
    spoiler_comment_dict = load_spoiler_dict()
    # get the mods of the sub so you can ignore them
    global subreddit_moderators
    subreddit_moderators = reddit.subreddit(PARSED_SUBREDDIT).moderator()

    #loli/shota tag checking
    database = Database()
    global nhentai
    nhentai = Nhentai(database)
    global tsumino
    tsumino = Tsumino(database)
    global ehentai
    ehentai = Ehentai(database)
    global bot
    bot = TagBot(None, database)

    # run_bot()
    while True:
        run_bot(reddit, cursor, db_conn)


def modqueue_loop(reddit, subreddit, cursor, db_conn):
    for item in reddit.subreddit(subreddit).mod.modqueue(limit=None):
        # do comment loops actions
        if item.name[:2] == 't1':
            print(item.body)
            
            # skip if author has no name
            if item.author:

                # automatically approve comments made by the bot
                if item.author.name == 'AnimemesBot' or item.author.name == 'AutoModerator':
                    item.mod.approve()
                    continue

                # automatically approve comments where the Sleuth couldn't find a repost
                if item.author.name == 'RepostSleuthBot':
                    if "I didn't find any posts that meet the matching requirements for r/Animemes. \n\nIt might be OC, it might not." in item.body:
                        item.mod.approve()
                        continue

                if item.author.name == 'DupeBro':
                    print('checking for similar matches with DupeBro')
                    check_dupebro_for_redundant_info(item)
                    continue

            # check if the comment is linking to loli content
            if check_for_sholi_links(item):
                continue

            # approve a comment if it is older than 3 minutes and contains a simple phrase
            if approve_non_ninja_simple_comments(item):
                continue

            # check of the comment has a broken spoiler
            # if check_for_broken_comment_spoilers(item):
            #     continue

            # remove comments from shadowbanned users and leave a comment for those users.
            # if remove_shadowbanned_comments(item):
            #     continue

        # do post loops acttions
        elif item.name[:2] == 't3':
            # if it is the weekend approve reaction memes
            if datetime.datetime.now().weekday() > 4:
                approve_weekend_reaction_meme_reposts(item, reddit)

            # Automatically approve memes reported for reaction meme on the weekend.
            approve_weekend_reaction_memes(item, cursor, db_conn)

            # Automatically approve memes that got reported for not having a spoiler, but have gotten tagged in the meantime.
            approve_flagged_but_now_spoiler_tagged_memes(item)
        
        #update user flairs with changes.
        check_flairs_and_update_if_different(item, cursor, db_conn)

        #update awards
        update_awards(item, reddit, cursor, db_conn)


def approve_non_ninja_simple_comments(comment):
    if comment.user_reports:
        return False
    if convert_time(comment.created_utc) + datetime.timedelta(minutes=3) > datetime.datetime.now():
        return False
    reported_by_automod = comment.mod_reports and any(mod_report[1] == 'AutoModerator' and 'Comments require manual review' in mod_report[0] for mod_report in comment.mod_reports)
    reported_by_sachi = comment.mod_reports and any(mod_report[1] == "SachiMod" and "manually approved" in mod_report[0] for mod_report in comment.mod_reports)

    if reported_by_automod or (reported_by_automod and reported_by_sachi):
        if comment.body.lower() in common_phrases_list:
            print(f"Approving common phrase: {comment.body}")
            comment.mod.approve()
            return True
    return False
    


def modlog_loop(reddit, subreddit, cursor, db_conn):
    curr_actions = []
    for action in reddit.subreddit(subreddit).mod.log(limit=None):
        update_watched_id_set(action, cursor, db_conn)
        cursor.execute("SELECT * FROM modlog WHERE id = %s", [action.id])
        exists = cursor.fetchone()
        if exists:
            break
        cursor.execute("INSERT INTO modlog (action, created_utc, description, details, id, mod, mod_id36, sr_id36, subreddit, subreddit_name_prefixed, target_author, target_body, target_fullname, target_permalink, target_title) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", (action.action, convert_time(action.created_utc), action.description, action.details, action.id, str(action.mod), action.mod_id36, action.sr_id36, action.subreddit, action.subreddit_name_prefixed, str(action.target_author), action.target_body, action.target_fullname, action.target_permalink, action.target_title))
        db_conn.commit()
        curr_actions.append(action)
    curr_actions.reverse()
    for action in curr_actions:
        update_user_comment_approvals(action, cursor, db_conn)


def update_user_comment_approvals(action, cursor, db_conn):
    robots = ['AutoModerator', 'SachiMod', 'AnimemesBot']
    if str(action.mod) not in robots:
        if action.action in ['removecomment', 'approvecomment']:
            cursor.execute("INSERT INTO comment_removals (target_fullname, author, created_utc, approved) VALUES (%s, %s, %s, %s) ON CONFLICT (target_fullname) DO UPDATE SET created_utc = EXCLUDED.created_utc, approved = EXCLUDED.approved", (action.target_fullname, str(action.target_author), convert_time(action.created_utc), (action.action == 'approvecomment')))

        

def update_watched_id_set(action, cursor, db_conn):
    if watched_id_set:
        if action and action.target_fullname and action.target_fullname[:2] == "t3":
            if action.target_fullname[3:] in watched_id_set:
                cursor.execute("SELECT timestamp FROM repost_report_check WHERE id = %s", [action.target_fullname[3:]])
                time = cursor.fetchone()[0]
                action_time = datetime.datetime.utcfromtimestamp(action.created_utc)
                if time < action_time:
                    watched_id_set.remove(action.target_fullname[3:])
                    update_db(action.target_fullname[3:], watched_id_report_dict.pop(action.target_fullname[3:]), cursor, db_conn)


def update_flairs_in_the_db(reddit, cursor, db_conn):
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
            try:
                if removal_suspect.link_flair_template_id:
                    pass
            except AttributeError:
                continue
            cursor.execute("UPDATE posts SET link_flair_template_id = %s, link_flair_text = %s WHERE id = %s", (removal_suspect.link_flair_template_id, removal_suspect.link_flair_text, removal_suspect.id))
            # Automated bans
            # automatic_ban_for_repeat_rule_breaking(reddit, cursor, removal_suspect)

            # Clean users with the proper flairs
            # purge_and_clean(removal_suspect, cursor)

            # Feed the event removals mirror db
            event_removal_db_update(removal_suspect, cursor)
        for entry in edit_flair_list:
            cursor.execute("UPDATE modlog SET ban_processing = true WHERE id = %s", (entry[0],))
        db_conn.commit()


def automatic_ban_for_repeat_rule_breaking(reddit, cursor, removal_suspect):
    # Auto ban people having their posts removed again after being banned previously
    # cursor.execute("SELECT created_utc, target_author FROM modlog WHERE target_author = (SELECT target_author FROM modlog WHERE target_fullname = %s AND NOT mod = 'SachiMod' LIMIT 1) AND action = 'banuser' AND created_utc > '2020-08-03' AND created_utc < (now() at time zone 'utc') - interval '1 day' ORDER BY created_utc DESC", (removal_suspect.name,))
    # previous_bans = cursor.fetchall()

    cursor.execute("""SELECT DISTINCT ON (target_fullname) target_fullname, target_author, created_utc
            FROM modlog
            WHERE target_author = (SELECT target_author FROM modlog WHERE target_fullname = %s LIMIT 1)
            AND NOT (mod = 'SachiMod' or mod = 'TheVexedGermanBot' or mod = 'LucyHeartfilia_Bot' or mod = 'AutoModerator')
            AND action = 'removelink'
            AND created_utc > '2020-09-08'
            AND NOT EXISTS (SELECT id FROM posts WHERE id = SUBSTRING(modlog.target_fullname, 4) AND link_flair_template_id = '094ce764-898a-11e9-b1bf-0e66eeae092c')
            AND EXISTS (SELECT id FROM posts WHERE id = SUBSTRING(modlog.target_fullname, 4) AND link_flair_template_id IS NOT NULL)
            ORDER BY target_fullname""",
            (removal_suspect.name,))

    removals = cursor.fetchall()
    if len(removals) > 1:
        cursor.execute("SELECT target_author, description, details FROM modlog WHERE action = 'banuser' AND mod = 'SachiMod' AND created_utc > '2020-09-08' and target_author = %s", (removals[0][1],))
        previous_bans = cursor.fetchall()
        ban_length = [1, 3, 7, 14, 30, 0][len(previous_bans)]
        # Make sure user is not banned already
        if not list(reddit.subreddit("Animemes").banned(removals[0][1])):
            ban_user(reddit, removals[0][1], duration=ban_length, note=f"Automated ban for repeatedly breaking the rules", ban_message = f'It appears you have created another rule breaking post after being {"warned" if len(previous_bans) == 0 else "banned"} previously. {"Please take some time to familiarize yourself with [our rules](https://www.reddit.com/r/Animemes/wiki/extendedrules) before posting again." if len(previous_bans) < 5 else ""}', ban_reason="Automated ban")
            print(f"User: {removals[0][1]} banned")


def purge_and_clean(removal_suspect, cursor):
    if removal_suspect.link_flair_template_id == 'c5b88c96-e32f-11ea-b51f-0e4c27b0997b' or removal_suspect.link_flair_template_id == '3672f04c-e3a9-11ea-9692-0e5b9ada98e5':
        kind = 'purge' if removal_suspect.link_flair_template_id == 'c5b88c96-e32f-11ea-b51f-0e4c27b0997b' else 'clean'
        db = psycopg2.connect(
            host = postgres_credentials_modque.HOST,
            database = "burning_bridges",
            user = postgres_credentials_modque.USER,
            password = postgres_credentials_modque.PASSWORD
            )
        cur = db.cursor()
        print(removal_suspect.id)
        cursor.execute("SELECT author FROM posts WHERE id = %s", (removal_suspect.id,))
        author = cursor.fetchone()
        cur.execute("SELECT client_id FROM client_registration ORDER BY case when busy then remaining_api_calls end desc, heartbeat desc LIMIT 1")
        client_id = cur.fetchone()
        print(author)
        print(client_id)
        if client_id and author:
            cur.execute("INSERT INTO jobs (client_id, \"user\", finished, type) VALUES (%s, %s, False, %s)", (client_id[0], author[0], kind))
            cur.execute("UPDATE client_registration SET busy = True WHERE client_id = %s", (client_id[0],))
        db.commit()
        cur.close()
        db.close()


def ban_user(reddit, user, ban_reason = "NRN: Reposted a meme", ban_message = 'Looks like someone did not understand the ["No Repost" part of "No Repost November"](https://www.reddit.com/r/Animemes/comments/dpwdn5/_/f5z3txs/) and should have some sense [smacked into them](https://i.imgur.com/4VsscZB.png). See you in three days\n\nMake sure to check your post hasn\'t been posted before on Animemes. Try using the reverse image search from google and "site:reddit.com" to do so. Making OC, however, is the best way to avoid posting a repost.', duration = 3, note = "Automated ban for reposting a meme"):
    reddit.subreddit(PARSED_SUBREDDIT).banned.add(user, ban_reason=ban_reason, ban_message=ban_message, duration=duration, note=note)

def event_removal_db_update(removal_suspect, cursor):
    # Event removal flair ID
    if removal_suspect.link_flair_template_id == 'eeaebb92-8b38-11ea-a432-0e232b3ed13d':
        cursor.execute("SELECT id, created_utc, mod FROM modlog WHERE target_fullname = %s AND action = 'removelink' ORDER BY created_utc DESC", (removal_suspect.name,))
        log_entry = cursor.fetchone()
        if log_entry:
            # event needs to be fed with the event name so it shows up properly
            cursor.execute("INSERT INTO event_removals (id, created_utc, mod, target_id, event) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (ID) DO NOTHING", (log_entry[0], log_entry[1], log_entry[2], removal_suspect.id, "NSFW Spoiler"))


def approve_no_dignity_repost_reports(reports, cursor, db_conn):
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
                        update_db(reports.id, report_dict, cursor, db_conn)
                        print("No approval")
                        approve = False
                        break
                    approve = True
            # approve the post and go back to the beginning of the loop        
            if approve:
                print("Approved")
                reports.mod.approve()
                update_db(reports.id, report_dict, cursor, db_conn)
                return
    except AttributeError:
        pass


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


def remove_shadowbanned_comments(comment):
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
                return True
    except AttributeError:
        return False



def check_for_sholi_links(comment):
    has_numbers, has_redaction = check_for_violation(comment.body)
    if has_numbers:
        if not has_redaction:
            print("Approving Comment")
            comment.mod.approve()
            return True
        else:
            print("Removing Comment")
            comment.mod.remove(spam=False, mod_note='Sholi link')
            return True
    return False


def check_for_broken_comment_spoilers(comment):
    broken_spoiler = re.search(r'(?<!(`|\\))>!\s+', comment.body)
    if broken_spoiler:
        reply = comment.reply(SPOILER_REMOVAL_COMMENT)
        reply.mod.distinguish(how='yes')
        comment.mod.remove(mod_note="Incorrectly formatted spoiler")
        if spoiler_comment_dict.get(comment.id):
            spoiler_comment_dict[comment.id] = datetime.datetime.now()
        else:
            spoiler_comment_dict.update({comment.id: datetime.datetime.now()})
        save_spoiler_dict(spoiler_comment_dict)
        return True
    return False

def gilded_posts_loop(reddit, subreddit, cursor, db_conn):
    for post in reddit.subreddit(subreddit).gilded(limit=100):
        update_awards(post, reddit, cursor, db_conn)
        check_flairs_and_update_if_different(post, cursor, db_conn)


def hot_posts_loop(reddit, subreddit, cursor, db_conn):
    for post in reddit.subreddit(subreddit).hot(limit=100):
        update_awards(post, reddit, cursor, db_conn)
        #update user flairs with changes.
        check_flairs_and_update_if_different(post, cursor, db_conn)


def update_awards(post, reddit, cursor, db_conn):
    try:
        if post.all_awardings:
            pass
    except:
        return
    cursor.execute("SELECT DISTINCT award_id, count(*) FROM awards_history WHERE post_id = %s GROUP BY award_id", (post.id,))
    old_awards = cursor.fetchall()
    old_awards_dict = {}
    for oa in old_awards:
        old_awards_dict.update({oa[0]: oa[1]})
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
        #Check if the award already is in the DB
        if old_awards_dict.get(award['id']):
            #Set the number of iterations to the new - the old
            iterations = award['count']-old_awards_dict.get(award['id'])
        else:
            iterations = award['count']
        for i in range(iterations):
            # Add the award as many times as it already appears on the post
            try:
                cursor.execute("INSERT INTO awards_history (award_id, added_utc, post_id) VALUES (%s, %s, %s)", (award['id'], datetime.datetime.utcnow(), post.id))
                # if award['id'] == 'award_d360b82a-1152-42de-9f76-b3bf88d48a62':
                #     cursor.execute("UPDATE user_teams SET power_up = %s, power_up_timestamp = %s", ('Ganbare', datetime.datetime.utcnow()))
            except Exception as e:
                db_conn.rollback()
                print(traceback.format_exc())
            
            # # Maximum Useless
            # if award['id'] == 'award_3f0ee040-3403-4d15-9237-e2ced6a5c8e9':
            #     ban_user(reddit, post.author, "Got Maximum Useless Award", "You win some, you lose some. Seems like someone wanted you out of the idol contest so much they gave your post a Maximum Useless award, which at the moment does have the use of giving the recipient a temp ban. See you soon \^\_\^", 1, "Automated ban for getting Maximum Useless")
            
            # # Keke's Advertising Service
            # if award['id'] == 'award_5de77dd3-fea9-4e6f-83d9-1df07ada8eb1':
            #     try:
            #         if post.name[:2] == 't3':
            #             with open('pin_store.txt', 'r') as f:
            #                 old_id = f.readline()
            #             old_pin = reddit.submission(old_id)
            #             old_pin.mod.sticky(state=False)
            #             post.mod.sticky(state=True)
            #             with open('pin_store.txt', 'w') as f:
            #                 f.write(post.id)
            #     except Exception as e:
            #         print(traceback.format_exc())
        db_conn.commit()

def new_posts_loop(reddit, subreddit, cursor, db_conn):
    current_new_post_list = []
    for submission in reddit.subreddit(subreddit).new(limit=100):
        # make a list of current new posts
        current_new_post_list.append(submission.id)

        # check for spoiler formatted title but no spoiler tag
        # if '[oc]' not in submission.title.lower() and '[nsfw]' not in submission.title.lower() and '[redacted]' not in submission.title.lower() and '[' in submission.title and ']' in submission.title and not submission.spoiler:
        #     submission.report('Possibly missing spoiler tag')

        # check if the post is spoiler marked but not titled correctly:
        if check_for_improper_title_spoiler_marks(submission):
            continue

        # check if the post is nsfw tagged but not spoiler tagged:
        # check_for_nsfw_tagging(submission)

        # Check if the image is below the minimum resolution
        if check_for_minimum_image_size(submission, cursor):
            continue

    global new_post_list
    new_post_list = post_new_posts_loop(new_post_list, current_new_post_list, cursor)
    db_conn.commit()

def post_new_posts_loop(new_post_list, current_new_post_list, cursor):
    if new_post_list:
        # determine the offset between the old and the new list
        offset = get_offset(current_new_post_list, new_post_list)
        for i, entry in enumerate(new_post_list):
            # exit if the end of new list has been reached.
            if i + offset >= len(current_new_post_list):
                break
            else:
                # improve this so it doesn't automatically go to the next entry.
                # check if the ids are identical
                if entry != current_new_post_list[i+offset]:
                    print(f"{entry} was removed")
                    cursor.execute("UPDATE posts SET estimated_deletion_time = %s WHERE id = %s", (datetime.datetime.now(), entry))
                    # move the offset one back because the new list is now missing one entry.
                    offset += -1
    # set the new list to be the one checked next time
    return current_new_post_list

def check_for_minimum_image_size(submission, cursor):
    cursor.execute("SELECT count(*) FROM sachimod_ignore_posts WHERE id = %s", (submission.id,))
    skip_count = cursor.fetchone()
    if skip_count and skip_count[0] > 0:
        return False
    # cursor.execute("SELECT id FROM sachimod_ignore_posts WHERE created_utc > %s", (datetime.datetime.now()-datetime.timedelta(days=1),))
    # stored_ignore = cursor.fetchall()
    # if stored_ignore:
    #     ignore_list = [entry[0] for entry in stored_ignore]
    # if submission.id not in ignore_list:
    try:
        if submission.preview:
            try:
                if submission.preview.get('images'):
                    res = submission.preview['images'][0]
                    if res['source']['height'] * res['source']['width'] < 100000:
                        submission.mod.remove()
                        submission.flair.select('c87c2ac6-1dd4-11ea-9a24-0ea0ae2c9561', text="Rule 6: Post Quality - Low Res")
                        return True
            except:
                print(traceback.format_exc())
    except AttributeError:
        # print(traceback.format_exc())
        print(f"Post {submission.id} has no preview")
    return False

        
def check_for_nsfw_tagging(submission):
    if submission.over_18:
        if '[nsfw]' not in submission.title.lower():
            submission.mod.remove()
            submission.flair.select('eeaebb92-8b38-11ea-a432-0e232b3ed13d')
        
def check_for_improper_title_spoiler_marks(submission):
    # check for spoiler tag but not properly formatted title
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
                    return False
            else:
                print(f"Removing: {submission.title}")
                submission.mod.remove()
                # improperly marked spoiler flair
                submission.flair.select("094ce764-898a-11e9-b1bf-0e66eeae092c")
                return True
    return False

def edited_comments_loop(reddit, subreddit, cursor, db_conn):
    # cursor.execute("SELECT comment_id, comment_edited FROM edited_comments_repo ORDER BY comment_edited desc")
    # latest_edited = cursor.fetchone()
    for comment in reddit.subreddit(subreddit).mod.edited(only='comments', limit=100):
        # Skip handling if the comment is made by a sub mod
        if comment.author in subreddit_moderators:
            continue
        # # Check for older edited spoiler tag broken comments
        # if comment.id in list(spoiler_comment_dict.keys()):
        #     check_if_broken_spoiler_is_fixed_and_approve(comment)

        # Remove any comment that if newer than the latest_edited
        # skip any comment and newer that already has an entry
        try:
            cursor.execute("INSERT INTO edited_comments_repo (comment_id, comment_edited, comment_body, parent_post_id, comment_username) VALUES (%s, %s, %s, %s, %s)", (comment.id, convert_time(comment.edited), comment.body, comment.submission.id, str(comment.author)))
            db_conn.commit()
            # comment.mod.remove()
        except psycopg2.errors.UniqueViolation:
            db_conn.rollback()
            break
        # if latest_edited and comment.id == latest_edited[0] and convert_time(comment.edited) == latest_edited[1]:
        #     break

        #update user flairs with changes.
        check_flairs_and_update_if_different(comment, cursor, db_conn)

def comments_loop(reddit, subreddit, cursor, db_conn):
    for comment in reddit.subreddit(subreddit).comments(limit=100):
        check_flairs_and_update_if_different(comment, cursor, db_conn)

def run_bot(reddit, cursor, db_conn):
    print("Current time: " + str(datetime.datetime.now().time()))
    # modqueue loop
    print("Fetching modqueue...")
    modqueue_loop(reddit, "Animemes", cursor, db_conn)
    # new posts loop
    print("Checking new")
    new_posts_loop(reddit, "Animemes", cursor, db_conn)

    # fetch the modlog
    print("Fetching modlog")
    modlog_loop(reddit, "Animemes", cursor, db_conn)

    print("Fetching New Modmail")
    new_modmail_fetcher(reddit, "Animemes", cursor, db_conn)
    # fetch modmail
    print("Fetching Modmail")
    modmail_fetcher(reddit, "Animemes", cursor, db_conn)

    # Update the post flairs in the DB
    print("Updating DB flairs")
    update_flairs_in_the_db(reddit, cursor, db_conn)

    # Get account messages and put them into the appropriate DB
    print("Getting mail")
    get_mail(reddit, cursor, db_conn)

    # gilded posts loop
    print("Checking gilded posts")
    gilded_posts_loop(reddit, "Animemes", cursor, db_conn)

    # hot posts loop
    print("Checking hot posts")
    hot_posts_loop(reddit, "Animemes", cursor, db_conn)
    
    print("Checking edited comments")
    edited_comments_loop(reddit, "Animemes", cursor, db_conn)

    print("Checking for edited broken spoiler comments")
    # check comments that are too new to show up in edited for spoiler updates
    # check_for_updated_comments(reddit)

    print("Checking new comments")
    comments_loop(reddit, "Animemes", cursor, db_conn)

    print(reddit.auth.limits)
    print("Sleeping for 30 seconds...")
    time.sleep(30)


def check_for_violation(comment):
    print("checkforviolation being run")
    numbers_combi = bot.scanForURL(comment)
    improper_nhentai_numbers = check_for_improper_urls(comment)
    if numbers_combi and improper_nhentai_numbers:
        numbers_combi += improper_nhentai_numbers
    elif not numbers_combi and improper_nhentai_numbers:
        numbers_combi = improper_nhentai_numbers
    isRedacted = False
    if numbers_combi:
        for entry in numbers_combi:
            number = entry.get("number")
            key = entry.get("type")
            if key == 'nhentai':
                processedData = nhentai.analyseNumber(number)
            elif key == 'tsumino':
                processedData = tsumino.analyseNumber(number)
            elif key == 'ehentai':
                processedData = ehentai.analyseNumber(number)
            # elif key == hitomilaKey:
            #     processedData = hitomila.analyseNumber(number)
            if processedData.get('isRedacted'):
                isRedacted = True
                break
            if processedData.get('error'):
                return False, False
        return True, isRedacted
    return False, isRedacted


def get_offset(new, old):
    try:
        return new.index(old[0])
    except ValueError:
        return get_offset(new, old[1:])
        

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


def update_db(post_id, reports_dict, cursor, db_conn):
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

def approve_weekend_reaction_meme_reposts(reports, reddit):
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


def approve_weekend_reaction_memes(reports, cursor, db_conn):
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
                update_db(reports.id, report_dict, cursor, db_conn)
                print("No approval")
                approve = False
                break
            approve = True
        # approve the post and go back to the beginning of the loop        
    if approve and is_reaction:
        reports.mod.approve()
        update_db(reports.id, report_dict, cursor, db_conn)


def convert_time(time):
    if time:
        return datetime.datetime.utcfromtimestamp(time)
    return None


def modmail_fetcher(reddit, subreddit, cursor, db_conn):
    for message in reddit.subreddit(subreddit).mod.inbox(limit=None):
        cursor.execute("SELECT id, replies FROM modmail WHERE id = %s", [message.id])
        replies = [reply.id for reply in message.replies]
        exists = cursor.fetchone()
        if exists and exists[1] == message.replies:
            break
        cursor.execute("INSERT INTO modmail (id, created_utc, first_message_name, replies, subject, author, body, dest) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET replies = EXCLUDED.replies, dest = EXCLUDED.dest, sent_to_discord = false", (message.id, convert_time(message.created_utc), message.first_message_name, replies, message.subject, str(message.author), message.body, str(message.dest)))
        for reply in message.replies:
            cursor.execute("INSERT INTO modmail (id, created_utc, first_message_name, subject, author, parent_id, body) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING", (reply.id, convert_time(reply.created_utc), reply.first_message_name, reply.subject, str(reply.author), reply.parent_id, reply.body))
        db_conn.commit()
    # for message in reddit.subreddit(subreddit).mod.unread(limit=None):
    #     cursor.execute("INSERT INTO modmail (id, created_utc, subject, author, body, dest) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING", (message.id, convert_time(message.created_utc), message.subject, str(message.author), message.body, str(message.dest)))
    #     db_conn.commit()
    #     message.mark_read()

def new_modmail_fetcher(reddit, subreddit, cursor, db_conn):
    # check archives first since the others produce new archives.
    for conversation in reddit.subreddit(subreddit).modmail.conversations(limit=1000, state='archived'):
        exists = modmail_db_updater(conversation, reddit, cursor, db_conn)
        if exists:
            break
    for state in ['all', 'appeals']:    
        for conversation in reddit.subreddit(subreddit).modmail.conversations(limit=1000, state=state):
            modmail_db_updater(conversation, reddit, cursor, db_conn)
            if conversation.is_highlighted:
                continue
            if not conversation.last_user_update:
                continue
            if not conversation.last_mod_update:
                # Archive if user is ignored for 14 days.
                if datetime.datetime.strptime(conversation.last_updated, "%Y-%m-%dT%H:%M:%S.%f%z").timestamp() < (datetime.datetime.utcnow() - datetime.timedelta(days=14)).timestamp():
                    conversation.archive()
                continue
            if not conversation.last_updated:
                continue
            # Archive if latest reply is from a mod.
            if datetime.datetime.strptime(conversation.last_mod_update, "%Y-%m-%dT%H:%M:%S.%f%z").timestamp() > datetime.datetime.strptime(conversation.last_user_update, "%Y-%m-%dT%H:%M:%S.%f%z").timestamp():
                conversation.archive()
                continue
            # Archive if a mod answered and the last user reply is older than 7 days.
            if datetime.datetime.strptime(conversation.last_updated, "%Y-%m-%dT%H:%M:%S.%f%z").timestamp() < (datetime.datetime.utcnow() - datetime.timedelta(days=7)).timestamp():
                conversation.archive()
                continue

def modmail_db_updater(conversation, reddit, cursor, db_conn):
    if not conversation.legacy_first_message_id:
        return False
    message = reddit.inbox.message(conversation.legacy_first_message_id)
    cursor.execute("SELECT id, replies FROM modmail WHERE id = %s", [message.id])
    exists = cursor.fetchone()
    replies = [reply.id for reply in message.replies]
    if exists and exists[1] == message.replies:
        return True
    cursor.execute("INSERT INTO modmail (id, created_utc, replies, subject, author, body, dest, new_modmail_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET replies = EXCLUDED.replies, dest = EXCLUDED.dest, sent_to_discord = false", (message.id, convert_time(message.created_utc), replies, message.subject, str(message.author), message.body, str(message.dest), conversation.id))
    for reply in message.replies:
        cursor.execute("INSERT INTO modmail (id, created_utc, first_message_name, subject, author, parent_id, body, new_modmail_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING", (reply.id, convert_time(reply.created_utc), message.name, reply.subject, str(reply.author), reply.parent_id, reply.body, conversation.id))
    db_conn.commit()
    return False


def check_awards_membership(award):
    # just try to see if the key is in the dict
    if awards_dict.get(award['id']):
        return True
    return False


def get_awards_dict(cursor):
    dic = {}
    cursor.execute("SELECT id, name FROM awards")
    awards = cursor.fetchall()
    for award in awards:
        dic.update({award[0]: award[1]})
    return dic


def generate_awards_css():
    css_string = '\n'
    for key in awards_dict.keys():
        css_string += f'a.awarding-link[data-award-id$="{key[-6:]}"]:hover:before {{\n\tcontent: "{awards_dict[key]}";\n}}\n'
    return css_string


def get_mail(reddit, cursor, db_conn):
    for message in reddit.inbox.all(limit=None):
        cursor.execute("SELECT id, replies FROM sachimail WHERE id = %s", [message.id])
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

def check_for_updated_comments(reddit):
    # Check recent comments because ninja edits don't show up in the edited page.
    for comment_id in list(spoiler_comment_dict.keys()):
        if spoiler_comment_dict[comment_id] + datetime.timedelta(minutes=3) < datetime.datetime.now():
            comment = reddit.comment(id=comment_id)
            check_if_broken_spoiler_is_fixed_and_approve(comment)
    # clean up old comments that are unlikely to be edited.
    for key in list(spoiler_comment_dict.keys()):
        if spoiler_comment_dict[key] < (datetime.datetime.now() - datetime.timedelta(days=1)):
            del spoiler_comment_dict[key]
    save_spoiler_dict(spoiler_comment_dict)

def check_if_broken_spoiler_is_fixed_and_approve(comment):
    broken_spoiler = re.search(r'(?<!(`|\\))>!\s+', comment.body)
    if not broken_spoiler:
        comment.mod.approve()
        del spoiler_comment_dict[comment.id]

def check_flairs_and_update_if_different(flair_item, cursor, db_conn):
    if flair_item.author_flair_css_class or flair_item.author_flair_text:
        cursor.execute("SELECT flair_text, flair_css_class FROM user_flairs WHERE redditor = %s", (str(flair_item.author),))
        exists = cursor.fetchone()
        flair_text = flair_item.author_flair_text if flair_item.author_flair_text else ''
        flair_css_class = flair_item.author_flair_css_class if flair_item.author_flair_css_class else ''
        if exists and (exists[0] != flair_text or exists[1] != flair_css_class):
            cursor.execute("INSERT INTO user_flairs (redditor, flair_text, flair_css_class) VALUES (%s, %s, %s) ON CONFLICT (redditor) DO UPDATE SET redditor = EXCLUDED.redditor, flair_text = EXCLUDED.flair_text, flair_css_class = EXCLUDED.flair_css_class, sent_to_discord = False", (str(flair_item.author), flair_text, flair_css_class))
            db_conn.commit()
        elif not exists:
            cursor.execute("INSERT INTO user_flairs (redditor, flair_text, flair_css_class) VALUES (%s, %s, %s) ON CONFLICT (redditor) DO UPDATE SET redditor = EXCLUDED.redditor, flair_text = EXCLUDED.flair_text, flair_css_class = EXCLUDED.flair_css_class, sent_to_discord = False", (str(flair_item.author), flair_text, flair_css_class))
            db_conn.commit()


if __name__ == '__main__':
    while True:
        try:
            main()
        except Exception as e:
            print(traceback.format_exc())
            open("log.txt", 'a').write(f"{datetime.datetime.now().time()}:\n{traceback.format_exc()}\n")
            pass