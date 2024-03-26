from django.db import transaction
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from recipe_scrapers import scrape_me
from quantulum3 import parser
from apps.recipe.serializer import RecipeSerializer
from apps.user_auth.models import RecipeJarUser
from apps.shopping_list.models import (
    Items,
    ShoppingListCategory,
    ShoppingListItems,
)
from django.shortcuts import (
    render,
    get_object_or_404
)
from rest_framework.generics import (
    CreateAPIView,
    ListCreateAPIView,
)
from rest_framework import (
    status,
    permissions
)
from apps.recipe.models import (
    RecipeCategory,
    Recipe,
    RecipeIngredient,
    RecipeStep
)
from apps.recipe.utils import (
    parse_quantity_and_unit,
    extract_ingredient_name
)


class RecipeInformation(ViewSet):
    """
    Get recipe information from a web extension and save it to the database
    """
    serializer_class = RecipeSerializer
    permissions_classes = [permissions.IsAuthenticated]

    @action(methods=['post'], detail=False, url_path='get-recipe-category')
    def post(self, request, *args, **kwargs) -> Response:
        data = request.data
        user_apple_id = data.get('user_apple_id')

        if not user_apple_id:
            return Response(
                {'error': 'user_id are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            user = RecipeJarUser.objects.get(user_apple_id=user_apple_id)
        except RecipeJarUser.DoesNotExist:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        categories = RecipeCategory.objects.filter(user=user).order_by('-id')
        response_data = {
            'categories': self.serializer_class(categories, many=True).data
        }
        return Response(response_data, status=status.HTTP_200_OK)

    def list(self, request, *args, **kwargs) -> Response:
        data = request.data
        web_url = data.get('website_url')

        scraper = scrape_me(web_url)

        ingredients = []
        steps = []
        nutrients = {}

        for index, ingredient in enumerate(scraper.ingredients()):
            quantity, unit = parse_quantity_and_unit(ingredient)
            ingredient_name = extract_ingredient_name(ingredient)

            ingredients.append({
                'name': ingredient_name if ingredient_name else "There is no name",
                'quantity': quantity,
                'unit': unit,
                'order_number': index + 1,
            })

        for index, step in enumerate(scraper.instructions_list()):
            steps.append({
                'step': step,
                'order_number': index + 1,
            })

        for name, value in scraper.nutrients().items():
            nutrients[name] = value

        recipe = {
            'author': scraper.author(),
            'title': scraper.title(),
            'recipe_category': scraper.category(),
            'picture_url': scraper.image(),
            'ingredients': ingredients,
            'steps': steps,
            'nutrients': nutrients,
            'rating': scraper.ratings(),
        }
        response_data = {
            'recipe': recipe,
        }
        return Response(response_data, status=status.HTTP_200_OK)


class SaveRecipe(CreateAPIView):
    """
    Save recipe to the database
    """
    serializer_class = RecipeSerializer
    permissions_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs) -> Response:
        data = request.data
        try:
            user_apple_id = data.get('user_apple_id')
            recipe_category_id = data.get('recipe_category_id')
            is_editor_choice = data.get('is_editor_choice')
            shopping_list_category_id = data.get('shopping_list_category_id')
            add_to_shopping_list = data.get('add_to_shopping_list')
            recipe_name = data.get('recipe_name')
            recipe_time = data.get('recipe_time')
            image_url = data.get('image_url')
            ingredients = data.get('ingredients')
            steps = data.get('steps')

            if not user_apple_id or not recipe_category_id:
                return Response(
                    {'error': 'user_id and recipe_category_id  are required.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            user = get_object_or_404(
                RecipeJarUser,
                user_apple_id=user_apple_id
            )

            recipe_category = get_object_or_404(
                RecipeCategory,
                id=recipe_category_id,
                user=user
            )

            last_recipe_order_number = Recipe.objects.filter(
                recipe_category=recipe_category
            ).order_by('-order_number').values_list('order_number', flat=True).first() or 0

            new_recipe = Recipe.objects.create(
                recipe_category=recipe_category,
                title=recipe_name,
                time=recipe_time,
                picture_url=image_url,
                is_editor_choice=is_editor_choice,
                order_number=last_recipe_order_number + 1
            )
            with transaction.atomic():
                recipe_ingredients = []
                recipe_steps = []
                shopping_list_items = []
                for ingredient in ingredients:
                    item_name = ingredient.get('name')
                    item_quantity = ingredient.get('quantity')
                    item_unit = ingredient.get('unit')
                    item_order_number = ingredient.get('order_number')

                    item, _ = Items.objects.get_or_create(
                        name=item_name,
                    )
                    recipe_ingredients.append(
                        RecipeIngredient(
                            recipe=new_recipe,
                            items=item,
                            quantity=item_quantity,
                            unit=item_unit
                        )
                    )
                    if add_to_shopping_list:
                        shopping_category = ShoppingListCategory.objects.get(
                            id=shopping_list_category_id
                        )
                        shopping_list_items.append(
                            ShoppingListItems(
                                item_id=item.id,
                                shopping_list__shopping_list_category_id=shopping_category.id,
                                shopping_list__is_check=False,
                                shopping_list__order_number=item_order_number
                            )
                        )
                for step in steps:
                    step_description = step.get('description')
                    step_order_number = step.get('order_number')
                    recipe_steps.append(
                        RecipeStep(
                            recipe=new_recipe,
                            description=step_description,
                            order_number=step_order_number
                        )
                    )

                RecipeIngredient.objects.bulk_create(recipe_ingredients)
                RecipeStep.objects.bulk_create(recipe_steps)
                if shopping_list_items:
                    ShoppingListItems.objects.bulk_create(shopping_list_items)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {'message': 'Recipe saved successfully.'},
            status=status.HTTP_201_CREATED
        )
