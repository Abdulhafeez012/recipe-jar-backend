# Generated by Django 4.2.8 on 2024-03-17 01:57

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('user_auth', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RecipeCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=255)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recipeCategories', to='user_auth.recipejaruser')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Recipe',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('title', models.CharField(blank=True, max_length=100, null=True)),
                ('time', models.PositiveIntegerField(blank=True, null=True)),
                ('picture_url', models.URLField(blank=True, max_length=500, null=True)),
                ('video_url', models.URLField(blank=True, max_length=500, null=True)),
                ('video_image_url', models.URLField(blank=True, max_length=500, null=True)),
                ('video_title', models.CharField(blank=True, max_length=500, null=True)),
                ('video_duration', models.TimeField(blank=True, null=True)),
                ('video_channel_name', models.CharField(blank=True, max_length=500, null=True)),
                ('video_posted_date', models.DateTimeField(blank=True, null=True)),
                ('is_editor_choice', models.BooleanField(default=False)),
                ('recipe_category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recipes', to='recipe.recipecategory')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
