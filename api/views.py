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
            {'id': str(course['_id']), 'title': course['title']}
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
        # uploaded_file = req.POST.get['file']
        clerk_id = req.POST.get('clerk_id')
        title = req.POST.get('title')
        my_file = req.FILES['file']

        date = datetime.datetime.today()

        session = boto3.session.Session()
        s3_client = session.client(
            's3',
            endpoint_url=wasabi_endpoint_url,
            aws_access_key_id=wasabi_access_key,
            aws_secret_access_key=wasabi_secret_key
        )

        key = f'thumbnails/courses/{clerk_id}_{my_file.name}'
        s3_client.upload_file(
            my_file,   # Local file path
            'coursebucket',         # Bucket name in Wasabi
            key # Desired key (path) in Wasabi
        )
        

        if not clerk_id:
            print('No ClerkID')
            return JsonResponse({'error': 'clerk_id is required'})
        
        user = users_collection.find_one({'clerk_id': clerk_id})
        if not user:
            print('No User')
            return JsonResponse({'error': 'User not found'})

        # Will dynamically add enrolled gmails. 
        course = {
            "creator_id": clerk_id,
            "creator_name": user['name'],
            'title': title,
            "created_at": date,
            "enrolled": 0,
            "earned": Decimal128("0.00"),
            "domain": "",
            "published": False,
            "key": key
        }

        courses_collection.insert_one(course)

        return JsonResponse({'success': True}, status=200)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)