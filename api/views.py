from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from pymongo import MongoClient
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.conf import settings
import boto3
from botocore.exceptions import ClientError
from bson import ObjectId
from bson.decimal128 import Decimal128
from bson.json_util import dumps
import random
import traceback
import datetime

from django.views.decorators.csrf import csrf_exempt
from django.utils.crypto import get_random_string
from django.http import JsonResponse
from pymongo import MongoClient
from pymongo.errors import OperationFailure
import bcrypt
import json
import requests

client = MongoClient(f'{settings.MONGO_URI}')
db = client['Coursard']
courses_collection = db['Courses']
landings_collection = db['Landings']
modules_collection = db['Modules']
videos_collection = db['Videos']
users_collection = db['Users']
wasabi_access_key = settings.WASABI_ACCESS_KEY
wasabi_secret_key = settings.WASABI_SECRET_KEY
wasabi_endpoint_url = 'https://s3.us-east-1.wasabisys.com'
aws_access_key_id = settings.AWS_ACCESS_KEY_ID
aws_secret_access_key = settings.AWS_SECRET_ACCESS_KEY

s3 = boto3.client('s3', aws_access_key_id=aws_access_key_id,
                          aws_secret_access_key=aws_secret_access_key)
bucket_name = 'coursard'

@csrf_exempt
def main(req):
    return HttpResponse("Wsg")


@csrf_exempt
def course_options(req):
    print('recieved')
    try:
        data = json.loads(req.body.decode("utf-8"))
        clerk_id = data.get("clerk_id")

        if not clerk_id:
            print('No clerk_id')
            return JsonResponse({'error': 'clerk_id is required'}, status=400)

        # Query the courses collection for courses associated with the clerk_id
        courses = courses_collection.find({'creator_id': clerk_id})

        # Format the courses
        formatted_courses = [
            {'id': str(course['_id']), 'title': course['title'], 'thumbnail': course['thumbnail'] if "thumbnail" in course else ''}
            for course in courses
        ]

        return JsonResponse({'courses': formatted_courses}, status=200)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def add_course(req):
    try:
        print('recieved')
        clerk_id = req.POST.get('clerk_id')
        title = req.POST.get('title')
        my_file = req.FILES['file']

        date = datetime.datetime.today()

        key = f'thumbnails/{clerk_id}_{my_file.name}'

        s3.upload_fileobj(
            my_file,   # Local file path
            bucket_name,    
            key,
            ExtraArgs={'ACL': 'public-read'}
        )

        s3_url = f"https://{bucket_name}.s3.amazonaws.com/{key}"
        

        if not clerk_id:
            print('No ClerkID')
            return JsonResponse({'error': 'clerk_id is required'})
        
        user = users_collection.find_one({'clerk_id': clerk_id})
        if not user:
            print('No User')
            return JsonResponse({'error': 'User not found'})

        landing = {
            "creator_id": clerk_id, 
            "creator_name": user['name'],
            "title": '',
            "CTA_text": '',
            "CTA_color": '',
            "CTA_link": '',
            "banner_img": '',
            "landing_text": '',
            "module_img": '',
            "footer_img": '',
            "footer_text": '',
            "footer_link": '',
            "favicon": ''
        }
        created_landing = landings_collection.insert_one(landing)

        # Get the ObjectId of the inserted document
        landing_id = created_landing.inserted_id

        course = {
            "creator_id": clerk_id,
            "creator_name": user['name'],
            'title': title,
            "created_at": date,
            "enrolled": 0,
            "earned": Decimal128("0.00"),
            "domain": "",
            "published": False,
            "thumbnail": s3_url, 
            "landing": str(landing_id)
        }

        created_course = courses_collection.insert_one(course)

        # Get the ObjectId of the inserted course document
        course_id = created_course.inserted_id

        # Update the landing document with the course_id
        landings_collection.update_one(
            {'_id': landing_id},   # Filter by the landing document's _id
            {'$set': {'course_id': str(course_id)}}  # Set the course_id
)

        return JsonResponse({'success': True}, status=200)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def course_details(req):
    data = json.loads(req.body.decode("utf-8"))
    clerk_id = data.get("clerk_id")
    course_id = data.get("course_id")
    
    course = courses_collection.find_one({"_id": ObjectId(course_id), "creator_id": clerk_id })
    course['_id'] = str(course['_id'])
    course['earned'] = str(course['earned'])

    landing = landings_collection.find_one({"course_id": course_id, "creator_id": clerk_id })
    landing['_id'] = str(landing['_id'])

    return JsonResponse({'course': course, 'landing': landing}, safe=False)
