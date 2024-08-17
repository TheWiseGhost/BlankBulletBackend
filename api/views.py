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
from datetime import datetime

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

@csrf_exempt
def main(req):
    return HttpResponse("Wsg")


@csrf_exempt
def course_options(req):
    try:
        body = json.loads(req.body.decode('utf-8'))
        clerk_id = body.get('cherk_id')

        if not clerk_id:
            return JsonResponse({'error': 'user_id is required'}, status=400)

        # Query the courses collection for courses associated with the user_id
        courses = courses_collection.find({'clerk_id': clerk_id})

        # Format the courses
        formatted_courses = [
            {'id': str(course['_id']), 'name': course['name']}
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
        body = json.loads(req.body.decode('utf-8'))
        clerk_id = body.get('clerk_id')
        print(clerk_id)
        title = body.get('title')

        if price is None or price <= 0:
            price = "0.00"
        else:
            price = str(price)

        date = datetime.date.today()
        

        if not clerk_id:
            return JsonResponse({'error': 'user_id is required'}, status=400)
        
        user = users_collection.find_one({'clerk_id': clerk_id})
        if not user:
            return JsonResponse({'error': 'User not found'}, status=400)

        # Will dynamically add enrolled gmails. 
        course = {
            "creator_id": clerk_id,
            "creator_name": user['name'],
            'title': title,
            "created_at": date,
            "enrolled": 0,
            "earned": Decimal128("0.00"),
            "price": Decimal128(price),
            "domain": "",
            "published": False,
        }

        courses_collection.insert_one(course)

        return JsonResponse({'success': True}, status=200)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)