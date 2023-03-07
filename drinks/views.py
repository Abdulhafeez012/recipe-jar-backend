import unicodedata
from .serializer import IngredientSerializer, RecipeSerializer, RecipeCategorySerializer
from .models import User, Recipe, Ingredient, Step, RecipeCategory, Unit, Item
from pytube import YouTube
from googleapiclient.discovery import build
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import json
from django.http import JsonResponse, HttpResponseBadRequest
from recipe_scrapers import scrape_me
from uuid import UUID, uuid4
from quantulum3 import parser
from ingredient_parser.en import parse
from django.shortcuts import render


def home(request):
    context = {'title': 'Whisk App'}
    return render(request, 'whiskTemplates/home.html', context)


@api_view(['POST'])
def create_user(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        user_uuid = uuid4()
        user = User(
            id=user_uuid,
            firstName=data['firstName'],
            lastName=data['lastName'],
            phoneNumber=data['phoneNumber'],
            age=data['age'],
            dateOfBirth=data['dateOfBirth'],
            weight=data['weight'],
            height=data['height'],
        )
        user.save()
        return JsonResponse({'message': 'User created successfully'})


@api_view(['POST'])
def create_recipe_category(request):
    if request.method == 'POST':
        data = json.loads(request.body)

        # reformat the data
        category_uuid = uuid4()
        name = data['name']
        user_id = data['userID']
        temp_user = User.objects.get(pk=user_id)
        categories = RecipeCategory.objects.filter(user=temp_user).order_by('orderID')
        order_id = len(categories) + 1

        temp_category = RecipeCategory(
            id=category_uuid,
            name=name,
            orderID=order_id,
            user=temp_user
        )

        temp_category.save()
        return JsonResponse({'message': 'Category created successfully'})


@api_view(['POST'])
def get_all_categories(request):
    user_id = request.data.get('userID')
    if not user_id:
        return Response({"error": "userID is required."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({"error": f"User with ID {user_id} does not exist."}, status=status.HTTP_404_NOT_FOUND)
    categories = RecipeCategory.objects.filter(user=user).order_by('orderID')
    serializer = RecipeCategorySerializer(categories, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
def save_recipe_two(request):
    # global item_from_db, unit_from_db
    if request.method == 'POST':
        try:
            # Parse the request body
            data = json.loads(request.body)
            category_id = UUID(data['categoryID'])
            recipe_name = data['name']
            time = data['time']
            picture_url = data['pictureUrl']
            video_url = data['videoUrl']['youtubeLink']
            video_image = data['videoUrl']['image']
            video_title = data['videoUrl']['title']
            is_editor_choice = data['isEditorChoice']
            ingredients = data['ingredients']
            steps = data['steps']

            # Check if the category exists in the database
            category = RecipeCategory.objects.get(pk=category_id)

            # Get existing recipes in the same category
            existing_recipes = Recipe.objects.filter(category=category)

            # Set the orderID for the new recipe
            order_id = len(existing_recipes) + 1
            # Create the recipe instance
            recipe = Recipe(id=uuid4(), title=recipe_name, time=time, pictureUrl=picture_url,
                            videoUrl=video_url, videoImage=video_image, videoTitle=video_title,
                            is_editor_choice=is_editor_choice, category=category, orderID=order_id)
            recipe.save()

            # Loop over the ingredients and create their related models if they do not exist
            for ingredient in ingredients:
                item_name = ingredient['name']
                quantity = ingredient['quantity']
                unit_name = ingredient['unit']
                order_id = ingredient['orderID']

                # Check if the item exists in the database or create a new one
                # items_length = Item.objects.count()
                # item, created = Item.objects.get_or_create(id=items_length+1, name=item_name)
                
                try:
                    item_from_db = Item.objects.get(name=item_name)
                    item = item_from_db
                except Item.DoesNotExist:
                    items_length = Item.objects.count()
                    item = Item(id=items_length + 1, name=item_name)
                    item.save()

                # if not item_from_db.DoesNotExist:
                #     items_length = Item.objects.count()
                #     item = Item(id=items_length + 1, name=item_name)
                #     item.save()
                # else:
                #     item = item_from_db


                # item = Item.objects.create(name=item_name)

                # Check if the unit exists in the database or create a new on
                if unit_name:
                    try:
                        unit_from_db = Unit.objects.get(name=unit_name)
                        unit = unit_from_db
                    except Unit.DoesNotExist:
                        unit_length = Unit.objects.count()
                        unit = Unit(id=unit_length + 1, name=unit_name)
                        unit.save()
                else:
                    unit = None

                ingredient_id = uuid4()
                # Create the ingredient instance
                ingredient = Ingredient(id=ingredient_id, itemID=item, quantity=quantity, unitID=unit,
                                        recipe=recipe, orderNumber=order_id)
                ingredient.save()

            # Loop over the steps and create their related models
            for step in steps:
                description = step['name']
                order_id = step['orderID']

                # Create the step instance
                step = Step(id=uuid4(), description=description, orderID=order_id, recipe=recipe)
                step.save()

            # Return a success response
            return JsonResponse({'message': 'Recipe saved successfully.'}, status=201)

        except (KeyError, ValueError, TypeError, RecipeCategory.DoesNotExist, Item.DoesNotExist):
            # Return an error response if the request is not properly formatted or the category or item do not exist
            return JsonResponse({'error': 'Invalid request.'}, status=400)

    # Return an error response if the request method is not POST
    return JsonResponse({'error': 'Invalid request method.'}, status=405)


@api_view(['POST'])
def get_recipe_information_web_extension(request):
    try:
        data = json.loads(request.body)
        website_url = data['websiteUrl']
        user_id = data['userID']
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"error": f"User with ID {user_id} does not exist."}, status=status.HTTP_404_NOT_FOUND)
        categories = RecipeCategory.objects.filter(user=user).order_by('orderID')
        serializer = RecipeCategorySerializer(categories, many=True)

        scraper = scrape_me(website_url)

        ingredients = []

        steps = []

        for ingredient in scraper.ingredients():
            quants = parser.parse(ingredient)
            if quants.__len__() == 0:
                quantity = None
                unit = ""
            else:
                quantity = quants[0].value
                unit = quants[0].unit.name

            if unit == 'dimensionless':
                unit = ""

            ingredient_parce_name = parse(convert_fraction(ingredient))

            ingredients.append(
                {
                    'name': ingredient_parce_name['name'],
                    'quantity': quantity,
                    'unit': unit,
                    'orderID': -1
                }
            )

        for step in scraper.instructions_list():
            steps.append(
                {
                    'name': step,
                    'orderID': -1
                }
            )

        recipe_data = {
            'name': scraper.title(),
            'time': scraper.total_time(),
            'pictureUrl': scraper.image(),
            'videoUrl': get_video(scraper.title()),
            'isEditorChoice': False,
            'ingredients': ingredients,
            'steps': steps
        }

        all_data = {
            'recipe': recipe_data,
            "categories": serializer.data
        }
        return Response(all_data, status=status.HTTP_201_CREATED, )
    except:
        return HttpResponseBadRequest("Scraping not supported for this URL")


def get_video(query):
    api_key = 'AIzaSyC1xBiPhp9D2UIh4dIeGjlex90s3BZ5me4'
    youtube = build('youtube', 'v3', developerKey=api_key)
    search_response = youtube.search().list(
        q=query + ' recipe',
        type='video',
        part='id,snippet',
        maxResults=30
    ).execute()
    max_views = 0
    link_of_max_views = ""
    title_of_max_views = ""
    image_of_max_views = ""
    for search_result in search_response.get('items', []):
        video_id = search_result['id']['videoId']
        video_url = f'https://www.youtube.com/watch?v={video_id}'
        video = YouTube(video_url)
        if video.views > max_views:
            max_views = video.views
            link_of_max_views = video_url
            title_of_max_views = video.title
            image_of_max_views = video.thumbnail_url
        else:
            break
    data = {
        'youtubeLink': link_of_max_views,
        'title': title_of_max_views,
        'image': image_of_max_views
    }
    return data


def convert_fraction(string):
    if '½' in string:
        fraction = unicodedata.numeric('½')
        string = string.replace('½', str(fraction))
    elif '¼' in string:
        fraction = unicodedata.numeric('¼')
        string = string.replace('¼', str(fraction))
    return string


# these all functions/views not used for now

@api_view(['POST'])
def recipe_information_customized(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            website_url = data['website_url']
            scraper = scrape_me(website_url)
            data = {
                'title': scraper.title(),
                'time': scraper.total_time(),
                'picture_url': scraper.image(),
                'is_editor_choice': True,
                'ingredients': scraper.ingredients()
            }
            return JsonResponse(data)
        except:
            return HttpResponseBadRequest("Bad Request: Invalid request body")
    else:
        return HttpResponseBadRequest("Bad Request: Only POST requests are allowed")


@api_view(['POST'])
def recipe_information_origin(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            website_url = data['website_url']
            scraper = scrape_me(website_url)
            return Response(scraper.to_json(), status=status.HTTP_201_CREATED, )
            # return Response(scraper.to_json(), status=status.HTTP_201_CREATED,)
        except:
            return HttpResponseBadRequest("Bad Request: Invalid request body")
    else:
        return HttpResponseBadRequest("Bad Request: Only POST requests are allowed")


@api_view(['POST'])
def ingredients_details(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        ingredient = data['ingredient']
        quants = parser.parse(ingredient)
        ingredient_parce_name = parse(convert_fraction(ingredient))

        data = {
            'name': ingredient_parce_name['name'],
            'quantity': quants[0].value,
            'unit': quants[0].unit.name,
        }
        return JsonResponse(data)
    else:
        return HttpResponseBadRequest("Bad Request: Only GET requests are allowed")


@api_view(['GET'])
def send_name(request, name):
    if request.method == 'GET':
        return JsonResponse({"name": name})
    else:
        return HttpResponseBadRequest("Bad Request: Only GET requests are allowed")