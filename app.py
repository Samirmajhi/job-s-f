from flask import Flask, request, render_template, redirect, abort, session, flash, make_response
from client_secret import client_secret, initial_html
from db import user_details_collection, onboarding_details_collection, jobs_details_collection, candidate_job_application_collection, chatbot_collection, resume_details_collection, profile_details_collection, saved_jobs_collection, chat_details_collection, connection_details_collection
from helpers import  query_update_billbot, add_html_to_db, analyze_resume, upload_file_firebase, extract_text_pdf, outbound_messages, next_build_status, updated_build_status, text_to_html, calculate_total_pages, mbsambsasmbsa
from jitsi import create_jwt
import os
from datetime import datetime
import requests
import pathlib
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests
import uuid
import time
import pusher

pusher_client = pusher.Pusher(
  app_id=os.environ['PUSHER_APP_ID'],
  key=os.environ['PUSHER_KEY'],
  secret=os.environ['PUSHER_SECRET'],
  cluster=os.environ['PUSHER_CLUSTER'],
  ssl=True
)

app = Flask(__name__)
app.secret_key = os.environ['APP_SECRET']

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

url_ = os.environ['APP_URL']

GOOGLE_CLIENT_ID = os.environ['GOOGLE_CLIENT_ID']
client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "client_secret.json")

flow = Flow.from_client_config(
    client_config=client_secret,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email", "openid"],
    redirect_uri=f"{url_}/callback"
)

def login_is_required(function):
    def wrapper(*args, **kwargs):
        if "google_id" not in session:
            return redirect("/") 
        else:
            return function(*args, **kwargs)
    return wrapper

def is_candidate(function):
    def wrapper(*args, **kwargs):
        if "purpose" not in session:
            return abort(500)  
        else:
            purpose = session.get('purpose')
            if purpose == "candidate":
                return function(*args, **kwargs)
            else:
                abort(500, {"message":{"You are not a candidate."}})
    return wrapper

def is_hirer(function):
    def wrapper(*args, **kwargs):
        if "purpose" not in session:
            return abort(500)  
        else:
            purpose = session.get('purpose')
            print(purpose)
            if purpose == "hirer":
                return function(*args, **kwargs)
            else:
                abort(500, {"message":{"You are not a Hirer."}})
    return wrapper

def is_onboarded(function):
    def wrapper(*args, **kwargs):
        onboarded = session.get("onboarded")
        if onboarded:
            return function(*args, **kwargs)
        else:
            return redirect("/dashboard")
    return wrapper


@app.route("/about-us", methods = ['GET'])
def about_us():
    user_logged_in = False
    if session.get('google_id') is not None:
        user_logged_in = True
    user_name = session.get("name")
    resp = make_response(render_template("about_us.html", user_name=user_name, user_logged_in=user_logged_in))
    return resp

@app.route("/contact-us", methods = ['GET'])
def contact_us():
    user_logged_in = False
    if session.get('google_id') is not None:
        user_logged_in = True
    user_name = session.get("name")
    resp = make_response(render_template("contact_us.html", user_name=user_name, user_logged_in=user_logged_in))
    return resp
    
@app.route("/", methods = ['GET'])
def start():
    if session.get('google_id') is None:
        user_name = session.get("name")
        resp = make_response(render_template("index.html", user_name=user_name))
        return resp
    else:
        return redirect("/dashboard")
    
@app.route("/searchJobs",methods = ['GET'])   
def search_jobs():
    searched_for = request.args.get("search")
    logged_in = True
    if session.get('google_id') is None:
        logged_in = False
    if logged_in:
        return redirect("/dashboard")
    # pipeline = [
    #     {
    #         '$lookup': {
    #             'from': 'jobs_details', 
    #             'localField': 'job_id', 
    #             'foreignField': 'job_id', 
    #             'as': 'job_details'
    #         }
    #     }, 
    #     {
    #         '$project': {
    #             '_id': 0,
    #             'job_details._id': 0
    #         }
    #     }
    # ]
    pipeline = [
        {
            "$match": {
                "$or": [
                    {"job_title": {"$regex": searched_for, "$options": "i"}},
                    {"job_description": {"$regex": searched_for, "$options": "i"}},
                    {"job_type": {"$regex": searched_for, "$options": "i"}},
                    {"job_topics": {"$regex": searched_for, "$options": "i"}}
                ]
            }
        },
         {
            '$lookup': {
                'from': 'jobs_details', 
                'localField': 'job_id', 
                'foreignField': 'job_id', 
                'as': 'job_details'
            }
        }, 
        {
            '$project': {
                '_id': 0,
                'job_details._id': 0
            }
        }
    ]
    
    all_jobs = list(jobs_details_collection.aggregate(pipeline))
    return render_template('job_search.html', all_jobs=all_jobs, logged_in=logged_in)

@app.route("/signup", methods = ['GET'])
def signup():
    if session.get('google_id') is None:
        user_name = session.get("name")
        resp = make_response(render_template("signup.html", user_name=user_name))
        return resp
    else:
        return redirect("/dashboard")

@app.route("/alljobs", methods = ['GET'], endpoint='alljobs')
@is_candidate
@login_is_required
def alljobs():
    user_name = session.get("name")
    onboarded = session.get("onboarded")
    user_id = session.get("google_id")
    if onboarded == False:
        return redirect("/onboarding")
    onboarding_details = onboarding_details_collection.find_one({"user_id": user_id},{"_id": 0})
    resume_built = onboarding_details.get("resume_built")
    if not resume_built: 
        return redirect("/billbot")
    pageno = request.args.get("pageno")
    page_number = 1  # The page number you want to retrieve
    if pageno is not None:
        page_number = int(pageno)
    page_size = 7   # Number of documents per page
    total_elements = len(list(jobs_details_collection.find({},{"_id": 0})))
    total_pages = calculate_total_pages(total_elements, page_size)
    skip = (page_number - 1) * page_size
    pipeline = [
        {
            '$lookup': {
                'from': 'jobs_details', 
                'localField': 'job_id', 
                'foreignField': 'job_id', 
                'as': 'job_details'
            }
        }, 
        {
                '$lookup': {
                    'from': 'saved_jobs', 
                    'localField': 'job_id', 
                    'foreignField': 'job_id', 
                    'as': 'saved_jobs_details'
                }
            }, 
        {
            '$project': {
                '_id': 0,
                'job_details._id': 0
            }
        },
        {"$skip": skip},  # Skip documents based on the calculated skip value
        {"$limit": page_size}  # Limit the number of documents per page
    ]
    all_jobs = list(jobs_details_collection.aggregate(pipeline))
    # return all_applied_jobs
    return render_template('candidate_alljobs.html', user_name=user_name, onboarding_details=onboarding_details, all_jobs=all_jobs, total_pages=total_pages,page_number=page_number)


@app.route("/dashboard", methods = ['GET'], endpoint='dashboard')
@login_is_required
def dashboard():
    user_name = session.get("name")
    onboarded = session.get("onboarded")
    user_id = session.get("google_id")
    if onboarded == False:
        return redirect("/onboarding")
    onboarding_details = onboarding_details_collection.find_one({"user_id": user_id},{"_id": 0})
    purpose = onboarding_details.get("purpose")
    resume_built = onboarding_details.get("resume_built")
    if purpose == 'hirer':
        approved_by_admin = onboarding_details.get('approved_by_admin')
        if approved_by_admin:
            pageno = request.args.get("pageno")
            page_number = 1  # The page number you want to retrieve
            if pageno is not None:
                page_number = int(pageno)
            page_size = 7   # Number of documents per page
            total_elements = len(list(jobs_details_collection.find({"user_id": user_id},{"_id": 0})))
            total_pages = calculate_total_pages(total_elements, page_size)
            skip = (page_number - 1) * page_size
            pipeline = [
                   {'$match': {"user_id": user_id} },
                    {
                        '$project': {
                            '_id': 0,
                        }
                    },
                    {"$skip": skip},  # Skip documents based on the calculated skip value
                    {"$limit": page_size}  # Limit the number of documents per page
                ]
            all_jobs = list(jobs_details_collection.aggregate(pipeline))
            all_published_jobs = list(jobs_details_collection.find({"user_id": user_id, "status":"published"},{"_id": 0}))
            total_selected_candidates = list(candidate_job_application_collection.find({"hirer_id": user_id, "status":"Accepted"},{"_id": 0}))
            stats = {
                "total_jobs" : len(all_jobs),
                "total_published_jobs" : len(all_published_jobs),
                "total_selected_candidates" : len(total_selected_candidates)
            }
            return render_template('hirer_dashboard.html', user_name=user_name, onboarding_details=onboarding_details, all_jobs=all_jobs, stats=stats, total_pages=total_pages, page_number=page_number)
        else:
            return render_template('admin_approval_pending.html')
    else:
        if not resume_built: 
            return redirect("/billbot")
        resume_skills_string = resume_details_collection.find_one({'user_id': user_id}, {'skills': 1}).get("skills")
        resume_skills = [skill.strip().lower() for skill in resume_skills_string.split(',')]
        print(resume_skills)
        regex_patterns = []
        for skill in resume_skills:
            skill_words = skill.split()
            skill_pattern = '|'.join(skill_words)
            regex_patterns.append(skill_pattern)
        regex_pattern = '|'.join(regex_patterns)
        print(regex_pattern)
        length_pipeline = [
                 {
        '$match': {
            'status': 'published',
               '$or': [
                {'job_title': {'$regex': regex_pattern, '$options': 'i'}},
                {'job_description': {'$regex': regex_pattern, '$options': 'i'}},
                {'job_topics': {'$regex': regex_pattern, '$options': 'i'}},
            ]
        }
    }, 
            {
                '$project': {
                    '_id': 0
                }
            }
        ]

        pageno = request.args.get("pageno")
        page_number = 1  # The page number you want to retrieve
        if pageno is not None:
            page_number = int(pageno)
        page_size = 7   # Number of documents per page
        total_elements = len(list(jobs_details_collection.aggregate(length_pipeline)))
        total_pages = calculate_total_pages(total_elements, page_size)
        skip = (page_number - 1) * page_size
        pipeline = [
                 {
        '$match': {
            'status': 'published',
               '$or': [
                {'job_title': {'$regex': regex_pattern, '$options': 'i'}},
                {'job_description': {'$regex': regex_pattern, '$options': 'i'}},
                {'job_topics': {'$regex': regex_pattern, '$options': 'i'}},
            ]  # You may add other conditions to filter jobs if needed
        }
    },
            {
                '$lookup': {
                    'from': 'onboarding_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'user_details'
                }
            }, 
            {
                '$lookup': {
                    'from': 'saved_jobs', 
                    'localField': 'job_id', 
                    'foreignField': 'job_id', 
                    'as': 'saved_jobs_details'
                }
            }, 
            {
                '$project': {
                    '_id': 0
                }
            },
        {"$skip": skip},  # Skip documents based on the calculated skip value
        {"$limit": page_size}  # Limit the number of documents per page
        ]

        all_jobs = list(jobs_details_collection.aggregate(pipeline))
        all_updated_jobs = []
        for idx, job in enumerate(all_jobs):
            if applied := candidate_job_application_collection.find_one({"job_id": job.get("job_id"),"user_id":  user_id},{"_id": 0}):
                pass
            else:
                all_updated_jobs.append(job)
        profile_details = profile_details_collection.find_one({"user_id": user_id},{"_id": 0})
        return render_template('candidate_dashboard.html', user_name=user_name, onboarding_details=onboarding_details, all_jobs=all_updated_jobs, profile_details=profile_details, total_pages=total_pages, page_number=page_number)
    
@app.route("/applied_jobs", methods = ['GET'], endpoint='applied_jobs')
@login_is_required
@is_candidate
def applied_jobs():
    user_name = session.get("name")
    onboarded = session.get("onboarded")
    user_id = session.get("google_id")
    if onboarded == False:
        return redirect("/onboarding")
    onboarding_details = onboarding_details_collection.find_one({"user_id": user_id},{"_id": 0})
    resume_built = onboarding_details.get("resume_built")
    if not resume_built: 
        return redirect("/billbot")
    pageno = request.args.get("pageno")
    page_number = 1  # The page number you want to retrieve
    if pageno is not None:
        page_number = int(pageno)
    page_size = 7   # Number of documents per page
    length_pipeline = [
                {"$match": {"user_id": user_id}},
        {
            '$project': {
                '_id': 0
            }
        }
    ]
    total_elements = len(list(candidate_job_application_collection.aggregate(length_pipeline)))
    total_pages = calculate_total_pages(total_elements, page_size)
    skip = (page_number - 1) * page_size
    pipeline = [
                {"$match": {"user_id": user_id}},
        {
            '$lookup': {
                'from': 'jobs_details', 
                'localField': 'job_id', 
                'foreignField': 'job_id', 
                'as': 'job_details'
            }
        }, 
        {
            '$lookup': {
                'from': 'onboarding_details', 
                'localField': 'job_details.user_id', 
                'foreignField': 'user_id', 
                'as': 'user_details'
            }
        }, 
        {
            '$project': {
                '_id': 0,
                'job_details._id': 0,
                'user_details._id': 0
            }
        },
        {"$skip": skip},  # Skip documents based on the calculated skip value
        {"$limit": page_size}  # Limit the number of documents per page
    ]
    all_applied_jobs = list(candidate_job_application_collection.aggregate(pipeline))
    # return all_applied_jobs
    return render_template('applied_jobs.html', user_name=user_name, onboarding_details=onboarding_details, all_applied_jobs=all_applied_jobs, total_pages=total_pages, page_number=page_number)

@app.route("/saved_jobs", methods = ['GET', 'POST'], endpoint='saved_jobs')
@login_is_required
@is_candidate
def saved_jobs():
    user_name = session.get("name")
    onboarded = session.get("onboarded")
    user_id = session.get("google_id")
    if onboarded == False:
        return redirect("/onboarding")
    if request.method == 'POST':
        pass
    onboarding_details = onboarding_details_collection.find_one({"user_id": user_id},{"_id": 0})
    resume_built = onboarding_details.get("resume_built")
    if not resume_built: 
        return redirect("/billbot")
    pageno = request.args.get("pageno")
    page_number = 1  # The page number you want to retrieve
    if pageno is not None:
        page_number = int(pageno)
    page_size = 7   # Number of documents per page
    length_pipeline = [
                    {"$match": {"user_id": user_id}},
            {
                '$project': {
                    '_id': 0
                }
            }
        ]
    total_elements = len(list(saved_jobs_collection.aggregate(length_pipeline)))
    total_pages = calculate_total_pages(total_elements, page_size)
    skip = (page_number - 1) * page_size
    pipeline = [
                    {"$match": {"user_id": user_id}},
            {
                '$lookup': {
                    'from': 'jobs_details', 
                    'localField': 'job_id', 
                    'foreignField': 'job_id', 
                    'as': 'job_details'
                }
            }, 
                    {
            '$lookup': {
                'from': 'onboarding_details', 
                'localField': 'job_details.user_id', 
                'foreignField': 'user_id', 
                'as': 'user_details'
            }
        }, 
            {
                '$project': {
                    '_id': 0,
                    'job_details._id': 0,
                    'user_details._id': 0
                }
            },
            {"$skip": skip},  # Skip documents based on the calculated skip value
        {"$limit": page_size}  # Limit the number of documents per page
        ]
    all_saved_jobs = list(saved_jobs_collection.aggregate(pipeline))
    # return all_applied_jobs
    return render_template('saved_jobs.html', user_name=user_name, onboarding_details=onboarding_details, all_saved_jobs=all_saved_jobs,total_pages=total_pages, page_number=page_number)


@app.route("/profile", methods=['GET', 'POST'], endpoint='profile_update')
@login_is_required
@is_candidate
def profile_update():
    user_id = session.get("google_id")
    purpose = session.get("purpose")
    if request.method == 'POST':
        profile_data = dict(request.form)
        if 'description' in profile_data:
            profile_data['description'] = profile_data['description'].strip()
        if 'profile_pic' in request.files and str(request.files['profile_pic'].filename)!="":
            profile_pic = request.files['profile_pic']
            profile_pic_link = upload_file_firebase(profile_pic, f"{user_id}/profile_pic.png")
            print(profile_pic_link)
            print("uploaded")
            profile_data['profile_pic'] = profile_pic_link
        profile_details_collection.update_one({"user_id": user_id},{"$set": profile_data})
        return redirect('/profile')
    if profile_details := profile_details_collection.find_one({"user_id": user_id},{"_id": 0}):
        if purpose == 'candidate':
            return render_template('candidate_profile.html', profile_details=profile_details, user_id=user_id) 
        elif purpose == 'hirer':
            return render_template('hirer_profile.html', profile_details=profile_details)
        else:
            abort(500, {"message" : "candidate or hirer not found in the records."})
    else:
        abort(500, {"message": f"DB Error: Profile Details for user_id {user_id} not found."})


@app.route("/public/candidate/<string:user_id>", methods=['GET', 'POST'], endpoint='public_candidate_profile')
def public_candidate_profile(user_id):
    pipeline = [
            {"$match": {"user_id": user_id}},
            {
                '$lookup': {
                    'from': 'resume', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'resume_details'
                }
            }, 
            {
                '$project': {
                    '_id': 0,
                    'resume_details._id': 0
                }
            }
        ]
    if profile_details := list(profile_details_collection.aggregate(pipeline)):
        return render_template('public_candidate_profile.html', profile_details=profile_details) 
    else:
        abort(500, {"message": f"DB Error: Profile Details for user_id {user_id} not found."})


@app.route("/upload_intro_candidate", methods=['POST'], endpoint='upload_intro_candidate')
@login_is_required
@is_candidate
def upload_intro_candidate():
    user_id = session.get("google_id")
    if 'intro_video' in request.files and str(request.files['intro_video'].filename)!="":
        intro_video = request.files['intro_video']
        intro_video_link = upload_file_firebase(intro_video, f"{user_id}/intro_video.mp4")
        print(intro_video_link)
        print("uploaded")
        profile_details_collection.update_one({"user_id": user_id},{"$set": {"intro_video_link": intro_video_link}})
        return redirect('/profile')



@app.route("/login")
def login():
    if session.get('google_id') is None:
        authorization_url, state = flow.authorization_url()
        session["state"] = state
        return redirect(authorization_url)
    else:
        flash({'type':'error', 'data':"Your are already Logged In"})
        return redirect("/")


@app.route("/mbsa", methods = ['GET'])
def mbsa():
    return str(mbsambsasmbsa())

@app.route("/mbsai", methods = ['GET'])
def mbsa1():
    return render_template('mbsa.html')

@app.route("/logout", methods = ['GET'])
def logout():
    if "google_id" not in session:
        return redirect("/")
    all_keys = list(session.keys())
    for key in all_keys:
        session.pop(key)
    return redirect("/")

@app.route("/billbot", methods = ['GET', 'POST'], endpoint='chatbot')
@login_is_required
@is_candidate
def chatbot():
    user_id = session.get("google_id")
    if onboarding_details := onboarding_details_collection.find_one({"user_id": user_id}, {"_id": 0}):
        phase = onboarding_details.get('phase')
        build_status = onboarding_details.get('build_status')
        if phase == "1":
            # messages = list(chatbot_collection.find({},{"_id": 0}))
            resume_uploaded = False
            if profile_details := profile_details_collection.find_one({"user_id": user_id},{"_id": 0}):
                if 'resume_link' in profile_details:
                    resume_link = profile_details['resume_link']
                    resume_uploaded = True
            if resume_uploaded:
                messages = [{"user": "billbot","msg": "Hi, I am BillBot."}, {"user": "billbot", "msg": f"I see you have already uploaded a <a href={resume_link} target=_blank>Resume</a>. Click Yes, if you want to upload another resume and hit no to use BillBot to develope a resume using AI!"}]
            else:           
                messages = [{"user": "billbot","msg": "Hi, I am BillBot."}, {"user": "billbot", "msg": "Do you have a pre-built resume?"}]
            return render_template('chatbot.html', messages=messages)
        elif phase == "2":
            messages = outbound_messages(build_status)
            nxt_build_status = next_build_status(build_status)
            print(nxt_build_status)
            # messages = [{"user":"billbot","msg": "Hi, The right side of your screen will display your resume. You can give me instruction to build it in the chat."},{"user":"billbot","msg": "You can give me information regarding your inroduction, skills, experiences, achievements and projects. I will create a professional resume for you!"}]
            if resume_details := resume_details_collection.find_one({"user_id": user_id},{"_id": 0}):
                resume_html = resume_details.get("resume_html")
                resume_built = session.get("resume_built")
                return render_template('resume_builder.html', messages=messages, resume_html=resume_html, resume_built=resume_built, nxt_build_status=nxt_build_status) 
            else:
                abort(500,{"message":"Something went wrong! Contact ADMIN!"})

@app.route("/edit/mdresume", methods=['GET','POST'], endpoint="edit_mdresume")
@is_candidate
def edit_mdresume():
    user_id = session.get("google_id")
    if request.method == 'POST':
        form_data = dict(request.form)
        resume_html = form_data.get("resume_html")
        user_id = session.get("google_id")
        resume_details_collection.update_one({"user_id": user_id},{"$set": {"resume_html": resume_html}})
        analyze_resume(user_id)
        return redirect("/edit/mdresume")
    if resume_details := resume_details_collection.find_one({"user_id": user_id},{"_id": 0}):
        markdown = resume_details.get("resume_html")
        return render_template('resume_edit.html', markdown=markdown) 
    else:
        abort(500, {"messages": f"Resume Deatails for user_id {user_id} unavailable! Contact Admin!"})

@app.route("/resume_build", methods = ['POST'], endpoint='resume_build')
@is_candidate
def resume_build():
    user_id = session.get("google_id")
    form_data = dict(request.form)
    userMsg = form_data.get("msg")
    nxt_build_status = form_data.get("nxt_build_status")
    updated_build_status(user_id, nxt_build_status)
    nxt_build_status_ = next_build_status(nxt_build_status)
    html_code = query_update_billbot(user_id, userMsg, nxt_build_status_)
    add_html_to_db(user_id, html_code)
    return {"html_code" :str(html_code), "nxt_messages": outbound_messages(nxt_build_status), "nxt_build_status": nxt_build_status_}

@app.route("/current_build_status", methods = ['POST'], endpoint='current_build_status')
@is_candidate
def current_build_status():
    user_id = session.get("google_id")
    if onboarding_details := onboarding_details_collection.find_one({"user_id": user_id}):
        current_build_status = onboarding_details.get("build_status")
        return next_build_status(str(current_build_status))
    else:
        abort(500)

@app.route("/resume_built", methods = ['POST'], endpoint='resume_built')
@is_candidate
def resume_built():
    form_data = dict(request.form)
    resume_html = form_data.get("resume_html")
    user_id = session.get("google_id")
    onboarding_details_collection.update_one({"user_id": user_id},{"$set": {"resume_built": True}})
    resume_details_collection.update_one({"user_id": user_id},{"$set": {"resume_html": resume_html}})
    analyze_resume(user_id)
    return redirect("/dashboard")

@app.route('/resume_upload',methods = ['POST'], endpoint='resume_upload')
@is_candidate
def resume_upload():
    user_id = session.get("google_id")
    if 'resume' in request.files:
        resume = request.files['resume']
        resume_link = upload_file_firebase(resume, f"{user_id}/resume.pdf")
        data = {"resume_link": resume_link}
        if resume_details := resume_details_collection.find_one({"user_id": user_id},{"_id": 0}):
            print("user exists resume_details_collection")
            resume_details_collection.update_one({"user_id": user_id},{"$set": data})
        else:
            print("user does not exists resume_details_collection")
            resume_details_collection.insert_one({"user_id": user_id, "resume_link": resume_link})
        profile_details_collection.update_one({"user_id": user_id},{"$set": data})
        onboarding_details_collection.update_one({"user_id": user_id},{"$set": {"resume_built": True}})
        resume_text = extract_text_pdf(resume)
        analyze_resume(user_id, resume_text)
        return redirect("/dashboard")
    
@app.route('/update_resume',methods = ['POST'], endpoint='update_resume')
@is_candidate
def update_resume():
    user_id = session.get("google_id")
    if 'resume' in request.files:
        resume = request.files['resume']
        resume_link = upload_file_firebase(resume, f"{user_id}/resume.pdf")
        data = {"resume_link": resume_link}
        if resume_details := resume_details_collection.find_one({"user_id": user_id},{"_id": 0}):
            print("user exists resume_details_collection")
            resume_details_collection.update_one({"user_id": user_id},{"$set": data})
        else:
            print("user does not exists resume_details_collection")
            resume_details_collection.insert_one({"user_id": user_id, "resume_link": resume_link})
        profile_details_collection.update_one({"user_id": user_id},{"$set": data})
        resume_text = extract_text_pdf(resume)
        analyze_resume(user_id, resume_text)
        return redirect("/profile")
  
@app.route("/have_resume", methods = ['POST'], endpoint='have_resume')
@is_candidate
def have_resume():
    user_id = session.get("google_id")
    onboarding_details_collection.update_one({"user_id": user_id}, {"$set": {"phase": "2"}})
    resume_data = {"user_id": user_id,"resume_html":initial_html}
    resume_details_collection.insert_one(resume_data)
    return redirect("/billbot")


@app.route("/callback")
def callback():
    flow.fetch_token(authorization_response=request.url)

    if not session["state"] == request.args["state"]:
        abort(500)  # State does not match!

    credentials = flow.credentials
    
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID
    )
    print(id_info)
    # return redirect("/mbsa")
    user_id = id_info.get("sub")
    user_name = id_info.get("name")
    user_email = id_info.get("email")
    data = {
        "google_id": user_id,
        "name": user_name,
        "email": user_email,
        "onboarded": False,
    }
    session.update(data)
    pipeline = [
            {
                '$match': {
                    'user_id': str(user_id)
                }
            }, {
                '$lookup': {
                    'from': 'onboarding_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'onboarding_details'
                }
            }, {
                '$project': {
                    '_id': 0, 
                    'onboarding_details._id': 0
                }
            }
        ]
    
    if user_details := list(user_details_collection.aggregate(pipeline)):
        user_details = user_details[0]
        session["onboarded"] = user_details.get("onboarded")
        onboarding_details = user_details.get("onboarding_details")
        if onboarding_details:
            onboarding_details = onboarding_details[0]
            session["purpose"] = onboarding_details.get("purpose")
            purpose = session["purpose"]
            if purpose and purpose == "candidate":
                session["resume_built"] = onboarding_details.get("resume_built")
    else:
        user_data = {
            "user_id": id_info.get("sub"),
            "user_name": id_info.get("name"),
            "email": id_info.get("email"),
            "joined_at": datetime.now(),
            "onboarded": False
        }
        session["onboarded"] = user_data.get("onboarded")
        user_details_collection.insert_one(user_data)
    return redirect("/")

@app.route("/onboarding", methods=['GET', 'POST'])
def onboarding():
    if request.method == 'POST':
        user_id = session.get('google_id')
        if  user_id is None:
            abort(401)
        else:
            onboarding_details = dict(request.form)
            onboarding_details['user_id'] = user_id
            if user_details := user_details_collection.find_one({"user_id": user_id},{"_id": 0}):
                if user_details.get("onboarded") == False:
                    purpose = onboarding_details.get("purpose")
                    session['purpose'] = purpose
                    data = {"onboarded": True}
                    onboarding_details['status'] = "active"
                    if purpose and purpose == "candidate":
                        onboarding_details['phase'] = "1"
                        onboarding_details['build_status'] = "introduction"
                        onboarding_details['resume_built'] = False
                        session['resume_built'] = False
                        profile_data = {
                            "user_id": user_details.get("user_id"),
                            "name": onboarding_details.get("candidate_name"),
                            "email": user_details.get("email"),
                            "mobno": onboarding_details.get("candidate_mobno"),
                        }
                        profile_details_collection.insert_one(profile_data)
                    elif purpose and purpose == "hirer":
                        profile_data = {
                            "user_id": user_details.get("user_id"),
                            "company_name": onboarding_details.get("company_name"),
                            "email": user_details.get("email"),
                            "company_representative_mobno": onboarding_details.get("company_representative_mobno"),
                        }
                        if 'company_logo' in request.files and str(request.files['company_logo'].filename)!="":
                            company_logo = request.files['company_logo']
                            company_logo_link = upload_file_firebase(company_logo, f"{user_id}/company_logo.png")
                            print(company_logo_link)
                            print("uploaded")
                            profile_data['company_logo'] = company_logo_link
                        profile_details_collection.insert_one(profile_data)
                        onboarding_details['approved_by_admin'] = False
                    else:
                        abort(500, {"message": "Onboarding couldn't be completed due to some technical issue!"})
                    onboarding_details_collection.insert_one(onboarding_details)
                    user_details_collection.update_one({"user_id": user_id}, {"$set":data})
                    session['onboarded'] = True
                    return redirect("/dashboard") 
                else:
                    abort(500, {"message": "User already Onboarded."})
    onboarded = session.get('onboarded')
    if onboarded == True:
        purpose = session.get("purpose")
        return redirect("/dashboard")
    user_name = session.get("name")
    return render_template('onboarding.html', user_name=user_name)
    

@app.route('/create_job',methods=['POST'], endpoint="create_job")
@is_hirer
def create_job():
    user_id = session.get("google_id")
    job_id = str(uuid.uuid4())
    job_details = dict(request.form)
    job_details['user_id'] = user_id
    job_details['job_id'] = job_id
    job_details['created_on'] = datetime.now()
    jobs_details_collection.insert_one(job_details)
    return redirect("/dashboard")

@app.route('/edit/job/<string:job_id>', methods=['GET', 'POST'], endpoint="edit_job")
@login_is_required
@is_hirer
def edit_job(job_id):
    user_id = session.get("google_id")
    if request.method == 'POST':
        incoming_details = dict(request.form)
        jobs_details_collection.update_one({"user_id": str(user_id), "job_id": str(job_id)},{"$set": incoming_details})
        return redirect('/dashboard')
    if job_details := jobs_details_collection.find_one({"user_id": str(user_id), "job_id": str(job_id)},{"_id": 0}):
        return render_template("job_details.html", job_details=job_details)
    
@app.route('/delete/job/<string:job_id>', methods=['POST'], endpoint="delete_job")
@login_is_required
@is_hirer
def delete_job(job_id):
    user_id = session.get("google_id")
    if request.method == 'POST':
        jobs_details_collection.delete_one({"user_id": str(user_id), "job_id": str(job_id)})
        return redirect('/dashboard')

@app.route('/save/job/<string:job_id>', methods=['POST'], endpoint="save_job")
@login_is_required
@is_candidate
def save_job(job_id):
    user_id = session.get("google_id")
    if _ := saved_jobs_collection.find_one({"user_id": user_id, "job_id": job_id},{"_id": 0}):
        return "error"
    else:
        saved_job_data = {
            "user_id": user_id,
            "job_id": job_id,
            "saved_on": datetime.now()
        }
        saved_jobs_collection.insert_one(saved_job_data)
        return {"status": "saved"}
    

@app.route('/remove_saved_job/<string:job_id>', methods=['POST'], endpoint="remove_saved_job")
@login_is_required
@is_candidate
def remove_saved_job(job_id):
    user_id = session.get("google_id")
    if _ := saved_jobs_collection.find_one({"user_id": user_id, "job_id": job_id},{"_id": 0}):
        saved_jobs_collection.delete_one({"user_id": user_id, "job_id": job_id})
        return {"status": "deleted"}
    else:
        return "error"


@app.route('/apply/job/<string:job_id>', methods=['GET', 'POST'], endpoint="apply_job")
@login_is_required
@is_candidate
def apply_job(job_id):
    user_id = session.get("google_id")
    if request.method == 'POST':
        if job_details := jobs_details_collection.find_one({"job_id": job_id},{"_id": 0}):
            job_apply_data = {
                "job_id": job_id,
                "hirer_id": job_details.get("user_id"),
                "user_id": user_id,
                "applied_on": datetime.now(),
                "status": "Applied",
            }
            candidate_job_application_collection.insert_one(job_apply_data)
            flash("Successfully Applied for the Job. Recruiters will get back to you soon, if you are a good fit.")
            return redirect(f'/apply/job/{job_id}')
        else:
            abort(500,{"messages": f"Job with Job Id {job_id} doesn't exist! "})
    pipeline = [
              {"$match": {"job_id": str(job_id)}},
                {
                    '$lookup': {
                        'from': 'onboarding_details', 
                        'localField': 'user_id', 
                        'foreignField': 'user_id', 
                        'as': 'user_details'
                    }
                }, 
                {
                    '$project': {
                        '_id': 0,
                        'user_details._id': 0
                    }
                }
            ]
    if job_details := list(jobs_details_collection.aggregate(pipeline)):
        job_details = job_details[0]
        if job_details.get("status") == "published":
            if candidate_job_application_collection.find_one({"user_id": user_id, "job_id": job_id},{"_id": 0}):
               applied = True 
            else:
                applied = False
            return render_template("apply_job.html", job_details=job_details, applied=applied)
        else:
            abort(500, {"message": f"JOB with job_id {job_id} not found!"})
    else:
        abort(500, {"message": f"JOB with job_id {job_id} not found!"})

@app.route("/status/job/<string:candidate_user_id>", methods=['POST'])
@login_is_required
@is_hirer
def change_job_status(candidate_user_id):
    form_data = dict(request.form)
    status = form_data.get("status")
    job_id = form_data.get("job_id")
    candidate_job_application_collection.update_one({"job_id": job_id, 'user_id': candidate_user_id},{"$set": {"status": status} })
    return redirect(f'/responses/job/{job_id}')


@app.route('/responses/job/<string:job_id>', methods=['GET', 'POST'], endpoint="job_responses")
@login_is_required
@is_hirer
@is_onboarded
def job_responses(job_id):
    if job_details := jobs_details_collection.find_one({"job_id": job_id},{"_id": 0, "job_title" :1, "mode_of_work": 1}):
        pageno = request.args.get("pageno")
        page_number = 1  # The page number you want to retrieve
        if pageno is not None:
            page_number = int(pageno)
        page_size = 7   # Number of documents per page
        total_elements = len(list(candidate_job_application_collection.find({"job_id": job_id})))
        total_pages = calculate_total_pages(total_elements, page_size)
        skip = (page_number - 1) * page_size
        pipeline = [
            {
                "$match": {"job_id": job_id}
            },
            {
                '$lookup': {
                    'from': 'onboarding_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'candidate_details'
                }
            },
            {
                '$lookup': {
                    'from': 'user_details', 
                    'localField': 'user_id', 
                    'foreignField': 'user_id', 
                    'as': 'user_details'
                }
            },
           {
        '$project': {
            '_id': 0, 
            'user_details._id': 0,
            'candidate_details._id': 0,
        },
    },
        {"$skip": skip},  # Skip documents based on the calculated skip value
        {"$limit": page_size}  # Limit the number of documents per page
        ]
        all_responses = list(candidate_job_application_collection.aggregate(pipeline))
        return render_template("job_responses.html", job_id=job_id, all_responses=all_responses, job_details=job_details, total_pages=total_pages, page_number=page_number)
    

@app.route("/chats", methods=['GET'], endpoint='all_chats')
@login_is_required
def all_chats():
    user_id = session.get("google_id")
    purpose = session.get("purpose")
    key = "hirer_id" if purpose == "hirer" else "candidate_id"
    localField = "hirer_id" if purpose == "candidate" else "candidate_id"
    localAs = "hirer_details" if purpose == "candidate" else "candidate_details"
    pipeline = [
         {
                "$match": {key: user_id}
            },
         {
                '$lookup': {
                    'from': 'onboarding_details', 
                    'localField': localField, 
                    'foreignField': 'user_id', 
                    'as': localAs
                }
            },
         {
                '$lookup': {
                    'from': 'jobs_details', 
                    'localField': "job_id", 
                    'foreignField': 'job_id', 
                    'as': "job_details"
                }
            },
            
           {
        '$project': {
            '_id': 0, 
            f'{localAs}._id': 0,
            'job_details._id': 0,
        }
    }
    ]
    all_connections = list(connection_details_collection.aggregate(pipeline))
    return render_template("chatservice/index.html", purpose=purpose, all_connections=all_connections)

import time
@app.route("/chat/<string:incoming_user_id>/<string:job_id>", methods=['GET', 'POST'], endpoint='specific_chat')
@login_is_required
def specific_chat(incoming_user_id, job_id):
    user_id = session.get("google_id")
    purpose = session.get("purpose")
    if request.method == 'POST':
        msg = dict(request.json).get('msg')
        chat_details = {
            "hirer_id": user_id if purpose == "hirer" else incoming_user_id,
            "candidate_id": user_id if purpose == "candidate" else incoming_user_id,
            "job_id": job_id,
            "sent_by": purpose,
            "sent_on": datetime.now(),
            "msg": msg,
        }
        chat_details_collection.insert_one(chat_details)
        channel_id = f"{user_id}_{incoming_user_id}_{job_id}" if purpose == "candidate" else f"{incoming_user_id}_{user_id}_{job_id}"
        pusher_client.trigger(channel_id, purpose, {'msg': msg})
        return {"status": "saved"}
    hirer_id = incoming_user_id if purpose == "candidate" else user_id
    candidate_id = user_id if purpose == "candidate" else incoming_user_id
    if onboarding_details := onboarding_details_collection.find_one({"user_id": incoming_user_id},{"_id": 0}):
        name = onboarding_details.get("company_name") if purpose == "candidate" else onboarding_details.get("candidate_name")
        pipeline = [
            {"$match": {"hirer_id": hirer_id, "candidate_id": candidate_id, "job_id": job_id}},
            {"$project": {"_id": 0}}
        ]
        all_chats = list(chat_details_collection.aggregate(pipeline))
        channel_id = f"{user_id}_{incoming_user_id}_{job_id}" if purpose == "candidate" else f"{incoming_user_id}_{user_id}_{job_id}"
        job_details = jobs_details_collection.find_one({"job_id": job_id},{"_id": 0,"job_title": 1})
        meet_details = {
            "meetLink": f"http://127.0.0.1:5000/meet/{channel_id}"
        }
        return render_template("chatservice/message.html",incoming_user_id=incoming_user_id, purpose=purpose, all_chats=all_chats, name=name, channel_id=channel_id, job_id=job_id, job_details=job_details, meet_details=meet_details, text_to_html=text_to_html)
    else:
        abort(500, {"message": "User Not Found!"})

@app.route("/initiate_chat", methods =['POST'], endpoint="initiate_chat")
@login_is_required
@is_hirer
def initiate_chat():
    user_id = session.get("google_id")
    form_data = dict(request.form)
    candidate_id = form_data.get("candidate_id")
    job_id = form_data.get("job_id")
    if connection_details := connection_details_collection.find_one({"candidate_id": candidate_id, "hirer_id": user_id},{"_id": 0}):
        pass
    else:
        if _ := candidate_job_application_collection.find_one({"user_id": candidate_id, "hirer_id": user_id, "job_id": job_id},{"_id": 0}):
            connection_details = {
            "created_on": datetime.now(),
            "hirer_id": user_id,
            "candidate_id": candidate_id,
            "job_id": job_id
            }
            connection_details_collection.insert_one(connection_details)
            candidate_job_application_collection.update_one({"user_id": candidate_id, "hirer_id": user_id, "job_id": job_id},{"$set": {"chat_initiated": True}})
        else:
            abort(500, {"message": "Either job_id or candidate_id is wrong!"})
    return redirect(f"/chat/{candidate_id}/{job_id}")
    
@app.route("/meet/<string:channel_id>", methods=['GET'], endpoint='meeting')
@login_is_required
def meeting(channel_id):
    purpose = session.get("purpose")
    candidate_id, hirer_id, job_id = channel_id.split("_")
    hirer_pipeline = [
           {
                "$match": {"user_id": hirer_id}
            },
         {
                '$lookup': {
                    'from': 'user_details', 
                    'localField': "user_id", 
                    'foreignField': 'user_id', 
                    'as': "user_details"
                }
            }
    ]
    candidate_pipeline = [
           {
                "$match": {"user_id": candidate_id}
            },
         {
                '$lookup': {
                    'from': 'user_details', 
                    'localField': "user_id", 
                    'foreignField': 'user_id', 
                    'as': "user_details"
                }
            }
    ]
    if onboarding_details := list(onboarding_details_collection.aggregate(hirer_pipeline)):
        company_name = onboarding_details[0].get("company_name")
        hirer_email = onboarding_details[0].get("user_details")[0]['email']
    else:
        abort(500, {"message": "Invalid Channel ID"})
    if onboarding_details := list(onboarding_details_collection.aggregate(candidate_pipeline)):
        candidate_name = onboarding_details[0].get("candidate_name")
        candidate_email = onboarding_details[0].get("user_details")[0]['email']
    else:
        abort(500, {"message": "Invalid Channel ID"})
    if job_details := jobs_details_collection.find_one({"job_id": job_id}, {"_id": 0, "job_title": 1}):
        if purpose == "hirer":
                jwt = create_jwt(company_name, hirer_email, True)
        else:
                jwt = create_jwt(candidate_name, candidate_email, False)
        meet_details = {
            "roomName": f"vpaas-magic-cookie-c1b5084297244909bc3d1d4dc2b51775/{channel_id}",
            "jwt": jwt,
            "meetLink": f"http:127.0.0.1:5000/meet/{channel_id}"
        }
        return render_template('videoservice/main.html', meet_details=meet_details, job_details=job_details, onboarding_details=onboarding_details)
    else:
        abort(500, {"message": "Invalid Channel ID"})

