from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
import bcrypt
import time
import datetime
from sqlalchemy import and_, or_, inspect as sqlalchemy_inspect, text
from datetime import date, timedelta
import inspect
import io
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key')

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL',
                                                  'sqlite:///fitness_app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    saved_workouts = db.relationship('UserSavedWorkout', backref='user', lazy=True)
    workout_progress = db.relationship('UserWorkoutProgress', backref='user', lazy=True)
    streak = db.relationship('UserStreak', backref='user', uselist=False, lazy=True)


class HealthCondition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)


class FitnessPriority(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    workouts = db.relationship('Workout', backref='fitness_priority', lazy=True)
    diets = db.relationship('Diet', backref='fitness_priority', lazy=True)


class Workout(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    duration = db.Column(db.Integer, nullable=False)  # Duration in minutes
    difficulty = db.Column(db.String(20), nullable=False)  # Beginner, Intermediate, Advanced
    fitness_priority_id = db.Column(db.Integer, db.ForeignKey('fitness_priority.id'), nullable=True)
    video_url = db.Column(db.String(255), nullable=True)  # URL to workout video
    improved_workout_id = db.Column(db.Integer, db.ForeignKey('workout.id'), nullable=True)  # Next level workout


class UserSavedWorkout(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    workout_id = db.Column(db.Integer, db.ForeignKey('workout.id'), nullable=False)
    date_saved = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    scheduled_date = db.Column(db.Date, nullable=True)
    workout = db.relationship('Workout')


class UserWorkoutProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    workout_id = db.Column(db.Integer, db.ForeignKey('workout.id'), nullable=False)
    completed_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    duration = db.Column(db.Integer)
    improved = db.Column(db.Boolean, default=False)
    rating = db.Column(db.Integer, nullable=True)
    intensity = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    workout = db.relationship('Workout')


class Diet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    calories = db.Column(db.Integer, nullable=False)
    fitness_priority_id = db.Column(db.Integer, db.ForeignKey('fitness_priority.id'))
    image_url = db.Column(db.String(255), nullable=True)
    tags = db.relationship('DietaryTag', secondary='diet_dietarytag_association', backref='diets')
    meal_plan = db.relationship('MealPlan', backref='diet', uselist=False, lazy=True)


class UserSavedDiet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    diet_id = db.Column(db.Integer, db.ForeignKey('diet.id'), nullable=False)
    date_saved = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    diet = db.relationship('Diet')


class UserStreak(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)
    current_streak = db.Column(db.Integer, default=0)
    longest_streak = db.Column(db.Integer, default=0)
    last_login = db.Column(db.Date)


workout_condition_exclusions = db.Table('workout_condition_exclusions',
                                        db.Column('workout_id', db.Integer, db.ForeignKey('workout.id'),
                                                  primary_key=True),
                                        db.Column('condition_id', db.Integer, db.ForeignKey('health_condition.id'),
                                                  primary_key=True)
                                        )



class DietaryTag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)


diet_dietarytag_association = db.Table('diet_dietarytag_association',
                                       db.Column('diet_id', db.Integer, db.ForeignKey('diet.id'), primary_key=True),
                                       db.Column('tag_id', db.Integer, db.ForeignKey('dietary_tag.id'),
                                                 primary_key=True)
                                       )



class MealPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    diet_id = db.Column(db.Integer, db.ForeignKey('diet.id'), nullable=False)
    breakfast = db.Column(db.Text, nullable=True)
    lunch = db.Column(db.Text, nullable=True)
    dinner = db.Column(db.Text, nullable=True)
    snacks = db.Column(db.Text, nullable=True)



def update_streak(user_id):
    try:
        today = date.today()
        user_streak = UserStreak.query.filter_by(user_id=user_id).first()
        if not user_streak:
            user_streak = UserStreak(user_id=user_id, current_streak=1, longest_streak=1, last_login=today)
            db.session.add(user_streak)
        else:
            last_login = user_streak.last_login
            if last_login == today:
                pass
            elif last_login == today - timedelta(days=1):
                user_streak.current_streak += 1
                if user_streak.current_streak > user_streak.longest_streak:
                    user_streak.longest_streak = user_streak.current_streak
                user_streak.last_login = today
            else:
                user_streak.current_streak = 1
                user_streak.last_login = today
        db.session.commit()
        return user_streak
    except Exception as e:
        print(f"Error updating streak: {str(e)}")
        return None

def has_completed_workout_on_date(user_id, date_):
    start_of_day = datetime.datetime.combine(date_, datetime.time.min)
    end_of_day = datetime.datetime.combine(date_, datetime.time.max)
    completed_workout = UserWorkoutProgress.query.filter(
        UserWorkoutProgress.user_id == user_id,
        UserWorkoutProgress.completed_date >= start_of_day,
        UserWorkoutProgress.completed_date <= end_of_day
    ).first()
    return completed_workout is not None

def initialize_required_tables():
    inspector = sqlalchemy_inspect(db.engine)
    tables = inspector.get_table_names()
    db.create_all()
    if 'health_condition' not in tables or not HealthCondition.query.first():
        init_db()

@app.route('/')
def home():
    return render_template('index.html', time=time)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            data = request.get_json()
            username = data.get('username')
            full_name = data.get('full_name')
            password = data.get('password')
            if not username or not full_name or not password:
                return jsonify({'error': 'All fields are required'}), 400
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                return jsonify({'error': 'Username already exists'}), 400
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            new_user = User(username=username, full_name=full_name, password_hash=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            try:
                initialize_required_tables()
            except:
                pass
            session['user_id'] = new_user.id
            try:
                streak = UserStreak(user_id=new_user.id, current_streak=1, longest_streak=1,
                                    last_login=datetime.datetime.now().date())
                db.session.add(streak)
                db.session.commit()
            except:
                db.session.rollback()
            return jsonify({'redirect_url': url_for('workout_finder')})
        except Exception as e:
            return jsonify({'error': f'Server error: {str(e)}'}), 500
    return render_template('signup.html', time=time)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
            if not username or not password:
                return jsonify({'error': 'Username and password are required'}), 400
            try:
                initialize_required_tables()
            except:
                pass
            user = User.query.filter_by(username=username).first()
            if not user:
                return jsonify({'error': 'Invalid username or password'}), 400
            if not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
                return jsonify({'error': 'Invalid username or password'}), 400
            session['user_id'] = user.id
            try:
                update_streak(user.id)
            except:
                pass
            return jsonify({'redirect_url': url_for('workout_finder')})
        except Exception as e:
            print(f"Login error: {str(e)}")
            return jsonify({'error': f'Server error: {str(e)}'}), 500
    return render_template('login.html', time=time)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
    try:
        db.session.execute(text("SELECT 1 FROM user_streak LIMIT 1"))
        db.session.execute(text("SELECT 1 FROM user_saved_workout LIMIT 1"))
        db.session.execute(text("SELECT 1 FROM user_workout_progress LIMIT 1"))
        streak = UserStreak.query.filter_by(user_id=user.id).first()
        if not streak:
            streak = update_streak(user.id)
        saved_workouts = UserSavedWorkout.query.filter_by(user_id=user.id).order_by(
            UserSavedWorkout.date_saved.desc()).limit(5).all()
        recent_progress = UserWorkoutProgress.query.filter_by(user_id=user.id).order_by(
            UserWorkoutProgress.completed_date.desc()).limit(5).all()
        today = date.today()
        upcoming_workouts = UserSavedWorkout.query.filter(
            UserSavedWorkout.user_id == user.id,
            UserSavedWorkout.scheduled_date >= today
        ).order_by(UserSavedWorkout.scheduled_date).limit(3).all()
        return render_template('dashboard.html',
                               user=user,
                               streak=streak,
                               saved_workouts=saved_workouts,
                               recent_progress=recent_progress,
                               upcoming_workouts=upcoming_workouts,
                               now=datetime.datetime.now(),
                               time=time)
    except Exception as e:
        print(f"Dashboard error: {str(e)}")
        return render_template('db_init_needed.html', time=time)

@app.route('/finder')
def workout_finder():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
    health_conditions = HealthCondition.query.all()
    fitness_priorities = FitnessPriority.query.all()
    return render_template('portal.html',
                           full_name=user.full_name,
                           health_conditions=health_conditions,
                           fitness_priorities=fitness_priorities,
                           time=time)

@app.route('/my-workouts')
def my_workouts():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
    saved_workouts = UserSavedWorkout.query.filter_by(user_id=user.id).order_by(
        UserSavedWorkout.date_saved.desc()).all()
    return render_template('my_workouts.html',
                           user=user,
                           saved_workouts=saved_workouts,
                           time=time)


@app.route('/diet-management')
def diet_management():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))

    init_dietary_tags()
    fitness_priorities = FitnessPriority.query.all()
    db_dietary_tags = DietaryTag.query.order_by(DietaryTag.name).all()
    dietary_tags = [{'id': tag.id, 'name': tag.name} for tag in db_dietary_tags]
    print(f"Loaded {len(dietary_tags)} dietary tags")
    for tag in dietary_tags:
        print(f"  - {tag['name']} (ID: {tag['id']})")

    return render_template('diet_management.html',
                           user=user,
                           fitness_priorities=fitness_priorities,
                           dietary_tags=dietary_tags,
                           time=time)


@app.route('/workout/<int:workout_id>')
def workout_timer(workout_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
    workout = Workout.query.get_or_404(workout_id)
    improved_workout = None
    if workout.improved_workout_id:
        improved_workout = Workout.query.get(workout.improved_workout_id)
    progress_history = UserWorkoutProgress.query.filter_by(
        user_id=user.id,
        workout_id=workout_id
    ).order_by(UserWorkoutProgress.completed_date.desc()).limit(5).all()
    return render_template('workout_timer.html',
                           user=user,
                           workout=workout,
                           improved_workout=improved_workout,
                           progress_history=progress_history,
                           time=time)


@app.route('/save-workout', methods=['POST'])
def save_workout():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        data = request.get_json()
        workout_id = data.get('workout_id')
        scheduled_date = data.get('scheduled_date')
        workout = Workout.query.get(workout_id)
        if not workout:
            return jsonify({'error': 'Workout not found'}), 404
        existing = UserSavedWorkout.query.filter_by(
            user_id=session['user_id'],
            workout_id=workout_id
        ).first()
        if existing:
            if scheduled_date:
                existing.scheduled_date = datetime.datetime.strptime(scheduled_date, '%Y-%m-%d').date()
                db.session.commit()
            return jsonify({'message': 'Workout updated successfully'})
        scheduled_date_obj = None
        if scheduled_date:
            scheduled_date_obj = datetime.datetime.strptime(scheduled_date, '%Y-%m-%d').date()
        saved_workout = UserSavedWorkout(
            user_id=session['user_id'],
            workout_id=workout_id,
            scheduled_date=scheduled_date_obj
        )
        db.session.add(saved_workout)
        db.session.commit()
        return jsonify({'message': 'Workout saved successfully'})
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/schedule-workout', methods=['POST'])
def schedule_workout():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        data = request.get_json()
        saved_workout_id = data.get('saved_workout_id')
        workout_id = data.get('workout_id')
        scheduled_date = data.get('scheduled_date')
        if not scheduled_date:
            return jsonify({'error': 'Scheduled date is required'}), 400
        if saved_workout_id:
            saved_workout = UserSavedWorkout.query.get(saved_workout_id)
            if not saved_workout or saved_workout.user_id != session['user_id']:
                return jsonify({'error': 'Workout not found or access denied'}), 404
            saved_workout.scheduled_date = datetime.datetime.strptime(scheduled_date, '%Y-%m-%d').date()
            db.session.commit()
            return jsonify({'message': 'Workout scheduled successfully'})
        elif workout_id:
            saved_workout = UserSavedWorkout.query.filter_by(
                user_id=session['user_id'],
                workout_id=workout_id
            ).first()
            if not saved_workout:
                w = Workout.query.get(workout_id)
                if not w:
                    return jsonify({'error': 'Workout not found'}), 404
                saved_workout = UserSavedWorkout(user_id=session['user_id'], workout_id=workout_id)
                db.session.add(saved_workout)
            saved_workout.scheduled_date = datetime.datetime.strptime(scheduled_date, '%Y-%m-%d').date()
            db.session.commit()
            return jsonify({'message': 'Workout scheduled successfully'})
        else:
            return jsonify({'error': 'Either saved_workout_id or workout_id is required'}), 400
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/remove-saved-workout', methods=['POST'])
def remove_saved_workout():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        data = request.get_json()
        saved_workout_id = data.get('saved_workout_id')
        if not saved_workout_id:
            return jsonify({'error': 'Missing required fields'}), 400
        saved_workout = UserSavedWorkout.query.get(saved_workout_id)
        if not saved_workout or saved_workout.user_id != session['user_id']:
            return jsonify({'error': 'Workout not found or access denied'}), 404
        db.session.delete(saved_workout)
        db.session.commit()
        return jsonify({'message': 'Workout removed successfully'})
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/complete-workout', methods=['POST'])
def complete_workout():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        data = request.get_json()
        workout_id = data.get('workout_id')
        duration = data.get('duration')
        improved = data.get('improved', False)
        rating = data.get('rating')
        intensity = data.get('intensity')
        notes = data.get('notes')
        if not workout_id or not duration:
            return jsonify({'error': 'Missing required fields'}), 400
        workout = Workout.query.get(workout_id)
        if not workout:
            return jsonify({'error': 'Workout not found'}), 404
        progress = UserWorkoutProgress(
            user_id=session['user_id'],
            workout_id=workout_id,
            duration=duration,
            improved=improved,
            rating=rating,
            intensity=intensity,
            notes=notes
        )
        db.session.add(progress)
        update_streak(session['user_id'])
        db.session.commit()
        return jsonify({'message': 'Workout completed successfully', 'progress_id': progress.id})
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/filter-diets', methods=['POST'])
def filter_diets():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    data = request.get_json()
    priority_id = data.get('priority', '')
    tag_ids = data.get('tags', [])
    query = Diet.query
    if priority_id:
        try:
            priority_id = int(priority_id)
            query = query.filter(Diet.fitness_priority_id == priority_id)
        except (ValueError, TypeError):
            pass

    if tag_ids and len(tag_ids) > 0:
        tag_ids = [int(tid) for tid in tag_ids if tid]

        for tag_id in tag_ids:
            query = query.filter(Diet.tags.any(DietaryTag.id == tag_id))
    diets = query.all()
    saved_diet_ids = [d.diet_id for d in UserSavedDiet.query.filter_by(user_id=session['user_id']).all()]
    diets_list = []
    for diet in diets:
        tags = [tag.name for tag in diet.tags]
        diet_data = {
            'id': diet.id,
            'name': diet.name,
            'description': diet.description,
            'calories': diet.calories,
            'image_url': diet.image_url if diet.image_url else "",
            'tags': tags,
            'is_saved': diet.id in saved_diet_ids
        }
        diets_list.append(diet_data)
    return jsonify({'diets': diets_list})


@app.route('/save-diet', methods=['POST'])
def save_diet():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        data = request.get_json()
        diet_id = data.get('diet_id')
        diet = Diet.query.get(diet_id)
        if not diet:
            return jsonify({'error': 'Diet not found'}), 404

        UserSavedDiet.query.filter_by(user_id=session['user_id']).delete()

        saved_diet = UserSavedDiet(user_id=session['user_id'], diet_id=diet_id)
        db.session.add(saved_diet)
        db.session.commit()
        return jsonify({'message': 'Diet saved successfully'})
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/remove-diet', methods=['POST'])
def remove_diet():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        data = request.get_json()
        diet_id = data.get('diet_id')

        saved_diet = UserSavedDiet.query.filter_by(
            user_id=session['user_id'],
            diet_id=diet_id
        ).first()

        if not saved_diet:
            return jsonify({'error': 'Diet not found or not saved by you'}), 404

        db.session.delete(saved_diet)
        db.session.commit()

        return jsonify({'message': 'Diet removed successfully'})
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/get-saved-diets')
def get_saved_diets():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    saved_diets = UserSavedDiet.query.filter_by(user_id=session['user_id']).all()
    diets_list = []

    for saved in saved_diets:
        diet = Diet.query.get(saved.diet_id)
        if diet:
            meal_plan_data = None
            meal_plan = MealPlan.query.filter_by(diet_id=diet.id).first()

            if meal_plan:
                # Convert pipe-delimited strings to proper arrays
                meal_plan_data = {
                    'breakfast': meal_plan.breakfast.split('|') if meal_plan.breakfast else [],
                    'lunch': meal_plan.lunch.split('|') if meal_plan.lunch else [],
                    'dinner': meal_plan.dinner.split('|') if meal_plan.dinner else [],
                    'snacks': meal_plan.snacks.split('|') if meal_plan.snacks else []
                }

            tags = [tag.name for tag in diet.tags]

            diets_list.append({
                'id': diet.id,
                'name': diet.name,
                'description': diet.description,
                'calories': diet.calories,
                'image_url': diet.image_url if diet.image_url else "",
                'tags': tags,
                'meal_plan': meal_plan_data,
                'saved_date': saved.date_saved.strftime('%Y-%m-%d')
            })

    return jsonify({'diets': diets_list})

@app.route('/download-diet-pdf/<int:diet_id>')
def download_diet_pdf(diet_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    saved_diet = UserSavedDiet.query.filter_by(user_id=session['user_id'], diet_id=diet_id).first()
    if not saved_diet:
        return jsonify({'error': 'Diet not found or not saved by you'}), 404

    diet = Diet.query.get(diet_id)
    if not diet:
        return jsonify({'error': 'Diet not found'}), 404

    meal_plan = MealPlan.query.filter_by(diet_id=diet.id).first()

    try:
        buffer = generate_diet_pdf(diet, meal_plan)
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"{diet.name.replace(' ', '_').lower()}_diet_plan.pdf"
        )
    except Exception as e:
        import traceback
        print(f"Error generating PDF: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'Error generating PDF: {str(e)}'}), 500


def generate_diet_pdf(diet, meal_plan=None):
    """
    Generate a PDF for a diet plan with accurate meal information
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=16,
        textColor=colors.HexColor('#C6AC48'),
        spaceAfter=12
    )

    section_title_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        textColor=colors.HexColor('#3A2831'),
        spaceBefore=12,
        spaceAfter=6
    )

    normal_style = styles['Normal']

    elements = []
    elements.append(Paragraph(f"{diet.name}", title_style))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph(f"Calories: {diet.calories} kcal", normal_style))

    if diet.tags:
        tag_text = "Tags: " + ", ".join([tag.name for tag in diet.tags])
        elements.append(Paragraph(tag_text, normal_style))

    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph(diet.description, normal_style))
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph("Daily Meal Plan", section_title_style))
    elements.append(Spacer(1, 0.1 * inch))


    breakfast_items = []
    lunch_items = []
    dinner_items = []
    snack_items = []

    if meal_plan:
        if meal_plan.breakfast:
            breakfast_items = meal_plan.breakfast.split('|')
        if meal_plan.lunch:
            lunch_items = meal_plan.lunch.split('|')
        if meal_plan.dinner:
            dinner_items = meal_plan.dinner.split('|')
        if meal_plan.snacks:
            snack_items = meal_plan.snacks.split('|')


    if not breakfast_items:
        if "High Protein" in diet.name:
            breakfast_items = [
                "Protein pancakes with banana (420 kcal)",
                "6 egg whites with spinach and turkey bacon (380 kcal)",
                "Protein shake with almond milk (300 kcal)"
            ]
        elif "Calorie Deficit" in diet.name:
            breakfast_items = [
                "Overnight oats with berries (280 kcal)",
                "Egg white omelet with vegetables (220 kcal)",
                "Smoothie with spinach and protein powder (250 kcal)"
            ]
        else:
            breakfast_items = [
                "Oatmeal with berries and nuts (350 kcal)",
                "Greek yogurt with honey (150 kcal)",
                "Whole grain toast with avocado (280 kcal)"
            ]

    if not lunch_items:
        if "High Protein" in diet.name:
            lunch_items = [
                "Grilled chicken breast with quinoa (550 kcal)",
                "Tuna salad with mixed greens (480 kcal)",
                "Turkey and avocado wrap (520 kcal)"
            ]
        elif "Calorie Deficit" in diet.name:
            lunch_items = [
                "Grilled chicken salad (320 kcal)",
                "Vegetable soup with side salad (280 kcal)",
                "Quinoa bowl with roasted vegetables (350 kcal)"
            ]
        else:
            lunch_items = [
                "Grilled chicken salad with olive oil dressing (450 kcal)",
                "Whole grain bread (120 kcal)",
                "Fresh fruit (80 kcal)"
            ]

    if not dinner_items:
        if "High Protein" in diet.name:
            dinner_items = [
                "Baked salmon with sweet potato (620 kcal)",
                "Lean beef stir fry with vegetables (580 kcal)",
                "Grilled steak with roasted vegetables (650 kcal)"
            ]
        elif "Calorie Deficit" in diet.name:
            dinner_items = [
                "Baked white fish with steamed broccoli (330 kcal)",
                "Turkey meatballs with zucchini noodles (370 kcal)",
                "Shrimp and vegetable stir fry (340 kcal)"
            ]
        else:
            dinner_items = [
                "Baked salmon with herbs (300 kcal)",
                "Steamed vegetables (150 kcal)",
                "Brown rice or quinoa (200 kcal)"
            ]

    if not snack_items:
        if "High Protein" in diet.name:
            snack_items = [
                "Greek yogurt with berries (150 kcal)",
                "Protein bar (200 kcal)",
                "Hard-boiled eggs (140 kcal)"
            ]
        elif "Calorie Deficit" in diet.name:
            snack_items = [
                "Apple slices with almond butter (150 kcal)",
                "Carrot sticks with hummus (120 kcal)",
                "Rice cakes with avocado (140 kcal)"
            ]
        else:
            snack_items = [
                "Handful of mixed nuts (200 kcal)",
                "Apple or other seasonal fruit (100 kcal)"
            ]


    elements.append(Paragraph("Breakfast:", section_title_style))
    for item in breakfast_items:
        elements.append(Paragraph(f"• {item}", normal_style))
    elements.append(Spacer(1, 0.2 * inch))

    elements.append(Paragraph("Lunch:", section_title_style))
    for item in lunch_items:
        elements.append(Paragraph(f"• {item}", normal_style))
    elements.append(Spacer(1, 0.2 * inch))

    elements.append(Paragraph("Dinner:", section_title_style))
    for item in dinner_items:
        elements.append(Paragraph(f"• {item}", normal_style))
    elements.append(Spacer(1, 0.2 * inch))

    elements.append(Paragraph("Snacks:", section_title_style))
    for item in snack_items:
        elements.append(Paragraph(f"• {item}", normal_style))


    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph("Nutritional Breakdown", section_title_style))
    nutritional_data = [
        ['Nutrient', 'Amount', 'Daily Value']
    ]

    if "High Protein" in diet.name:
        nutritional_data.extend([
            ['Protein', '180g', '360%'],
            ['Carbohydrates', '160g', '53%'],
            ['Fat', '80g', '123%'],
            ['Fiber', '25g', '100%']
        ])
    elif "Calorie Deficit" in diet.name:
        nutritional_data.extend([
            ['Protein', '120g', '240%'],
            ['Carbohydrates', '140g', '47%'],
            ['Fat', '50g', '77%'],
            ['Fiber', '30g', '120%']
        ])
    elif "Heart-Healthy" in diet.name or "Mediterranean" in diet.name:
        nutritional_data.extend([
            ['Protein', '110g', '220%'],
            ['Carbohydrates', '200g', '67%'],
            ['Fat', '75g', '115%'],
            ['Fiber', '35g', '140%']
        ])
    else:
        nutritional_data.extend([
            ['Protein', '120g', '240%'],
            ['Carbohydrates', '180g', '60%'],
            ['Fat', '65g', '100%'],
            ['Fiber', '30g', '120%']
        ])

    nutritional_table = Table(nutritional_data, colWidths=[2 * inch, 1 * inch, 1 * inch])
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3A2831')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ])

    nutritional_table.setStyle(table_style)
    elements.append(nutritional_table)
    elements.append(Spacer(1, 0.5 * inch))
    elements.append(Paragraph(f"Generated by FitAdapt on {datetime.datetime.now().strftime('%Y-%m-%d')}", normal_style))
    doc.build(elements)
    buffer.seek(0)
    return buffer


@app.route('/filter-workouts', methods=['POST'])
def filter_workouts():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    data = request.get_json()
    condition_ids = data.get('conditions', [])
    priority_id = data.get('priority', '')
    condition_ids = [int(cid) for cid in condition_ids if cid]
    if priority_id:
        priority_id = int(priority_id)
    query = Workout.query
    if priority_id:
        query = query.filter(Workout.fitness_priority_id == priority_id)
    if condition_ids:
        excluded_workout_ids = db.session.query(workout_condition_exclusions.c.workout_id).filter(
            workout_condition_exclusions.c.condition_id.in_(condition_ids)).all()
        excluded_workout_ids = [wid[0] for wid in excluded_workout_ids]
        if excluded_workout_ids:
            query = query.filter(~Workout.id.in_(excluded_workout_ids))
    workouts = query.all()
    saved_ids = [sw.workout_id for sw in UserSavedWorkout.query.filter_by(user_id=session['user_id']).all()]
    workouts_list = []
    for w in workouts:
        workouts_list.append({
            'id': w.id,
            'title': w.title,
            'description': w.description,
            'duration': w.duration,
            'difficulty': w.difficulty,
            'is_saved': w.id in saved_ids,
            'video_url': w.video_url
        })
    return jsonify({'workouts': workouts_list})



@app.route('/init-db')
def init_db():
    try:
        inspector = sqlalchemy_inspect(db.engine)
        tables_exist = inspector.get_table_names()
        users_exist = False
        if 'user' in tables_exist:
            users_exist = db.session.query(User.id).first() is not None
        existing_users = []
        if 'user' in tables_exist and users_exist:
            existing_users = User.query.all()
        db.create_all()
        if 'health_condition' not in tables_exist or not HealthCondition.query.first():
            conditions = [
                HealthCondition(name="Vertigo/Dizziness", description="Sensation of spinning or whirling"),
                HealthCondition(name="Lower Back Pain", description="Pain in the lumbar spine area"),
                HealthCondition(name="Knee Issues", description="Pain or discomfort in the knee joints"),
                HealthCondition(name="Hypertension", description="High blood pressure"),
                HealthCondition(name="Asthma", description="Respiratory condition causing breathing difficulty"),
                HealthCondition(name="Arthritis", description="Joint inflammation causing pain and stiffness"),
                HealthCondition(name="Heart Condition", description="Cardiovascular health concerns"),
                HealthCondition(name="Pregnancy", description="Expecting mothers"),
                HealthCondition(name="Diabetes", description="Blood sugar regulation issues")
            ]
            db.session.add_all(conditions)
            priorities = [
                FitnessPriority(name="Weight Loss", description="Focus on burning calories and fat reduction"),
                FitnessPriority(name="Muscle Building", description="Focus on strength and muscle growth"),
                FitnessPriority(name="Cardiovascular Health", description="Focus on heart health and endurance"),
                FitnessPriority(name="Flexibility", description="Focus on increasing range of motion"),
                FitnessPriority(name="Balance & Coordination", description="Focus on stability and body control")
            ]
            db.session.add_all(priorities)
            db.session.commit()
            workouts = [
                Workout(title="HIIT Fat Burner",
                        description="High-intensity interval training to maximize calorie burn",
                        duration=30, difficulty="Intermediate", fitness_priority_id=1,
                        video_url="https://www.youtube.com/embed/50kH47ZztHs"),
                Workout(title="Cardio Kickboxing",
                        description="Dynamic kickboxing moves to shed pounds while having fun",
                        duration=45, difficulty="Intermediate", fitness_priority_id=1,
                        video_url="https://www.youtube.com/embed/vZsQjHUPY04"),
                Workout(title="Beginner Weight Loss Circuit",
                        description="Simple circuit training designed for beginners focusing on full body movement",
                        duration=20, difficulty="Beginner", fitness_priority_id=1,
                        video_url="https://www.youtube.com/embed/dVQpKZpAF4s"),
                Workout(title="Advanced Fat Burn",
                        description="Intense full-body workout designed to maximize calorie burn and boost metabolism",
                        duration=40, difficulty="Advanced", fitness_priority_id=1,
                        video_url="https://www.youtube.com/embed/5U6Mz3hP6fo"),
                Workout(title="Low Impact Cardio",
                        description="Joint-friendly cardio workout great for beginners and those with knee issues",
                        duration=25, difficulty="Beginner", fitness_priority_id=1,
                        video_url="https://www.youtube.com/embed/OD2to6G3w5Q"),


                Workout(title="Bodyweight Muscle Builder",
                        description="Build muscle without equipment using progressive bodyweight exercises",
                        duration=35, difficulty="Intermediate", fitness_priority_id=2,
                        video_url="https://www.youtube.com/embed/NmB2DlO5Vn4"),
                Workout(title="Dumbbell Strength Training",
                        description="Comprehensive strength workout using just a pair of dumbbells",
                        duration=40, difficulty="Intermediate", fitness_priority_id=2,
                        video_url="https://www.youtube.com/embed/ocj09K0HpyA"),
                Workout(title="Beginner Strength Fundamentals",
                        description="Perfect introduction to strength training focusing on form and technique",
                        duration=30, difficulty="Beginner", fitness_priority_id=2,
                        video_url="https://www.youtube.com/embed/Y6S5P-QnY5I"),
                Workout(title="Advanced Muscle Hypertrophy",
                        description="Intensive workout designed to maximize muscle growth for experienced athletes",
                        duration=50, difficulty="Advanced", fitness_priority_id=2,
                        video_url="https://www.youtube.com/embed/oBLTOq9VtDw"),
                Workout(title="Core & Abs Builder",
                        description="Focused workout to strengthen your core and develop defined abs",
                        duration=20, difficulty="Intermediate", fitness_priority_id=2,
                        video_url="https://www.youtube.com/embed/mc3xsd8Y6Ro"),


                Workout(title="Heart-Healthy Cardio",
                        description="Moderate intensity steady-state cardio to improve heart and lung health",
                        duration=35, difficulty="Intermediate", fitness_priority_id=3,
                        video_url="https://www.youtube.com/embed/efQw8Eif8P4"),
                Workout(title="Beginner Cardio Starter",
                        description="Simple cardio routine perfect for those new to fitness",
                        duration=20, difficulty="Beginner", fitness_priority_id=3,
                        video_url="https://www.youtube.com/embed/14oTmNyBLao"),
                Workout(title="Advanced Cardio Intervals",
                        description="High-intensity cardio intervals to maximize cardiovascular benefits",
                        duration=40, difficulty="Advanced", fitness_priority_id=3,
                        video_url="https://www.youtube.com/embed/6Xq7MGlqx5A"),
                Workout(title="Low-Impact Endurance Builder",
                        description="Joint-friendly workout to build cardiovascular endurance",
                        duration=30, difficulty="Beginner", fitness_priority_id=3,
                        video_url="https://www.youtube.com/embed/4V1SioyVBMI"),
                Workout(title="Cardio Dance Workout",
                        description="Fun dance-based cardio to improve heart health while having fun",
                        duration=25, difficulty="Intermediate", fitness_priority_id=3,
                        video_url="https://www.youtube.com/embed/UcV3N69N7lA"),


                Workout(title="Full Body Stretch Routine",
                        description="Comprehensive stretching routine to improve overall flexibility",
                        duration=25, difficulty="Beginner", fitness_priority_id=4,
                        video_url="https://www.youtube.com/embed/4pKly2JojMw"),
                Workout(title="Yoga for Flexibility",
                        description="Yoga flow designed to increase range of motion and flexibility",
                        duration=30, difficulty="Intermediate", fitness_priority_id=4,
                        video_url="https://www.youtube.com/embed/TxRQ-vR0VKM"),
                Workout(title="Advanced Flexibility Training",
                        description="Deep stretching routine for those looking to significantly improve flexibility",
                        duration=40, difficulty="Advanced", fitness_priority_id=4,
                        video_url="https://www.youtube.com/embed/WkP6yfjky84"),
                Workout(title="Beginner Yoga Flow",
                        description="Gentle yoga sequence perfect for beginners to improve flexibility",
                        duration=20, difficulty="Beginner", fitness_priority_id=4,
                        video_url="https://www.youtube.com/embed/oXFx7_2aO7Y"),
                Workout(title="Dynamic Stretching Routine",
                        description="Active stretching to improve flexibility and prepare for exercise",
                        duration=15, difficulty="Intermediate", fitness_priority_id=4,
                        video_url="https://www.youtube.com/embed/C3F6mR7Q5Fk"),


                Workout(title="Balance Fundamentals",
                        description="Basic exercises to improve stability and balance",
                        duration=20, difficulty="Beginner", fitness_priority_id=5,
                        video_url="https://www.youtube.com/embed/kk9Bz5oO2Ac"),
                Workout(title="Core Stability & Balance",
                        description="Workout focusing on core strength to enhance balance",
                        duration=30, difficulty="Intermediate", fitness_priority_id=5,
                        video_url="https://www.youtube.com/embed/w5Pq-3l2G-g"),
                Workout(title="Advanced Balance Challenges",
                        description="Complex balance exercises for those looking for a serious challenge",
                        duration=35, difficulty="Advanced", fitness_priority_id=5,
                        video_url="https://www.youtube.com/embed/V9p7CrT4R0Q"),
                Workout(title="Functional Movement Training",
                        description="Exercises to improve coordination and body awareness",
                        duration=25, difficulty="Intermediate", fitness_priority_id=5,
                        video_url="https://www.youtube.com/embed/4p1ex3xGRYo"),
                Workout(title="Stability Ball Workout",
                        description="Using a stability ball to challenge and improve balance",
                        duration=20, difficulty="Beginner", fitness_priority_id=5,
                        video_url="https://www.youtube.com/embed/1W6a9wKDO7g")
            ]

            db.session.add_all(workouts)
            db.session.commit()

            diets = [
                Diet(name="High Protein Meal Plan",
                     description="Focused on muscle recovery and growth with lean proteins",
                     calories=2500, fitness_priority_id=2),
                Diet(name="Calorie Deficit Plan",
                     description="Balanced nutrition with reduced calories for weight loss",
                     calories=1800, fitness_priority_id=1),
                Diet(name="Heart-Healthy Mediterranean",
                     description="Rich in omega-3s and antioxidants for cardiovascular health",
                     calories=2200, fitness_priority_id=3),
                Diet(name="Anti-Inflammatory Diet",
                     description="Focuses on reducing inflammation and supporting joint health",
                     calories=2000, fitness_priority_id=4),
                Diet(name="Balanced Energy Diet",
                     description="Steady energy release for improved endurance and coordination",
                     calories=2300, fitness_priority_id=5)
            ]
            db.session.add_all(diets)
            db.session.commit()

        if not DietaryTag.query.first():
            sample_tags = [
                DietaryTag(name="Vegan"),
                DietaryTag(name="Vegetarian"),
                DietaryTag(name="Keto"),
                DietaryTag(name="Gluten-Free"),
                DietaryTag(name="High-Protein"),
                DietaryTag(name="Low-Carb")
            ]
            db.session.add_all(sample_tags)
            db.session.commit()
            vegan_tag = DietaryTag.query.filter_by(name="Vegan").first()
            keto_tag = DietaryTag.query.filter_by(name="Keto").first()
            high_protein_tag = DietaryTag.query.filter_by(name="High-Protein").first()
            diet_hp = Diet.query.filter_by(name="High Protein Meal Plan").first()
            if diet_hp and high_protein_tag:
                diet_hp.tags.append(high_protein_tag)
            diet_cd = Diet.query.filter_by(name="Calorie Deficit Plan").first()
            if diet_cd and keto_tag:
                diet_cd.tags.append(keto_tag)
            db.session.commit()

        try:
            init_meal_plans()
            print("Meal plans initialized successfully")
        except Exception as e:
            print(f"Error initializing meal plans: {str(e)}")

        return jsonify({'message': 'Database initialized successfully'})
    except Exception as e:
        return jsonify({'error': f'Database initialization error: {str(e)}'}), 500


def init_meal_plans():
    diets = Diet.query.all()
    for diet in diets:
        existing_plan = MealPlan.query.filter_by(diet_id=diet.id).first()
        if not existing_plan:

            breakfast = lunch = dinner = snacks = ""


            if "High Protein" in diet.name:
                breakfast = "Protein pancakes with banana (420 kcal)|Greek yogurt with berries and nuts (320 kcal)|6 egg whites with spinach and turkey bacon (380 kcal)|Protein shake with almond milk and frozen berries (300 kcal)"
                lunch = "Grilled chicken breast with quinoa and roasted vegetables (550 kcal)|Tuna salad with mixed greens and olive oil dressing (480 kcal)|Turkey and avocado wrap with whole grain tortilla (520 kcal)|Cottage cheese with fruit and almonds (380 kcal)"
                dinner = "Baked salmon with sweet potato and asparagus (620 kcal)|Lean beef stir fry with brown rice (580 kcal)|Grilled steak with roasted vegetables (650 kcal)|Baked chicken with wild rice and steamed broccoli (550 kcal)"
                snacks = "Greek yogurt with honey (150 kcal)|Protein bar (200 kcal)|Hard-boiled eggs (140 kcal)|Cottage cheese with berries (180 kcal)|Protein shake (180 kcal)"

            elif "Calorie Deficit" in diet.name:
                breakfast = "Overnight oats with berries (280 kcal)|Egg white omelet with vegetables (220 kcal)|Smoothie with spinach and protein powder (250 kcal)|Chia seed pudding with almond milk (240 kcal)"
                lunch = "Grilled chicken salad with light dressing (320 kcal)|Vegetable soup with side salad (280 kcal)|Quinoa bowl with roasted vegetables (350 kcal)|Turkey lettuce wraps (290 kcal)"
                dinner = "Baked white fish with steamed broccoli (330 kcal)|Turkey meatballs with zucchini noodles (370 kcal)|Shrimp and vegetable stir fry (340 kcal)|Cauliflower rice bowl with grilled chicken (360 kcal)"
                snacks = "Apple slices with 1 tbsp almond butter (150 kcal)|Carrot sticks with 2 tbsp hummus (120 kcal)|Rice cakes with avocado (140 kcal)|Plain Greek yogurt with cinnamon (100 kcal)"

            elif "Heart-Healthy" in diet.name or "Mediterranean" in diet.name:
                breakfast = "Greek yogurt with honey and walnuts (320 kcal)|Whole grain toast with olive oil and tomatoes (280 kcal)|Vegetable frittata with feta cheese (330 kcal)|Oatmeal with dried fruits and nuts (350 kcal)"
                lunch = "Mediterranean salad with chickpeas and olives (420 kcal)|Grilled fish with lemon and herbs (380 kcal)|Whole grain pita with hummus and vegetables (410 kcal)|Lentil soup with whole grain bread (390 kcal)"
                dinner = "Eggplant moussaka (480 kcal)|Grilled chicken with roasted Mediterranean vegetables (450 kcal)|Baked cod with tomato and olive sauce (420 kcal)|Bean and vegetable stew with whole grain bread (470 kcal)"
                snacks = "Handful of almonds (160 kcal)|Fresh fruit (100 kcal)|Olives (70 kcal)|Whole grain crackers with feta cheese (180 kcal)|Dates with walnuts (150 kcal)"

            elif "Anti-Inflammatory" in diet.name:
                breakfast = "Turmeric smoothie with ginger and berries (290 kcal)|Chia seed pudding with berries (270 kcal)|Avocado toast with poached egg on whole grain bread (340 kcal)|Anti-inflammatory oatmeal with cinnamon and berries (300 kcal)"
                lunch = "Salmon salad with leafy greens and olive oil (420 kcal)|Turmeric rice bowl with vegetables and tofu (380 kcal)|Lentil soup with spinach (350 kcal)|Buddha bowl with quinoa, avocado and vegetables (410 kcal)"
                dinner = "Baked fish with ginger and turmeric (390 kcal)|Roasted vegetable and quinoa bowl (370 kcal)|Chicken curry with anti-inflammatory spices (450 kcal)|Sweet potato and black bean chili (380 kcal)"
                snacks = "Blueberries and walnuts (140 kcal)|Pineapple slices (80 kcal)|Dark chocolate square (70 kcal)|Green tea with ginger (0 kcal)|Apple with cinnamon (80 kcal)"

            elif "Balanced Energy" in diet.name:
                breakfast = "Whole grain toast with peanut butter and banana (380 kcal)|Smoothie bowl with granola and mixed fruit (420 kcal)|Breakfast burrito with beans and vegetables (450 kcal)|Scrambled eggs with whole grain toast and avocado (390 kcal)"
                lunch = "Chicken and vegetable wrap (480 kcal)|Tuna pasta salad (450 kcal)|Rice bowl with beans and vegetables (470 kcal)|Sweet potato with black beans and corn (430 kcal)"
                dinner = "Brown rice with grilled fish and vegetables (520 kcal)|Whole wheat pasta with lean meat sauce (540 kcal)|Vegetable stir-fry with tofu and brown rice (490 kcal)|Baked chicken with quinoa and roasted vegetables (510 kcal)"
                snacks = "Trail mix (200 kcal)|Yogurt with granola (180 kcal)|Banana with peanut butter (240 kcal)|Energy bar (220 kcal)|Apple with cheese (170 kcal)"


            meal_plan = MealPlan(
                diet_id=diet.id,
                breakfast=breakfast,
                lunch=lunch,
                dinner=dinner,
                snacks=snacks
            )
            db.session.add(meal_plan)

    try:
        db.session.commit()
        print("Meal plans initialized successfully")
    except Exception as e:
        db.session.rollback()
        print(f"Error initializing meal plans: {str(e)}")


@app.route('/safe-init-db')
def safe_init_db():
    try:
        db.create_all()
        inspector = sqlalchemy_inspect(db.engine)
        tables = inspector.get_table_names()
        if 'health_condition' not in tables or not HealthCondition.query.first():
            conditions = [
                HealthCondition(name="Lower Back Pain", description="Pain in the lumbar spine area"),
                HealthCondition(name="Knee Issues", description="Pain or discomfort in the knee joints")
            ]
            for condition in conditions:
                try:
                    db.session.add(condition)
                    db.session.commit()
                except:
                    db.session.rollback()
            priorities = [
                FitnessPriority(name="Weight Loss", description="Focus on burning calories and fat reduction"),
                FitnessPriority(name="Strength", description="Focus on muscle building and strength")
            ]
            for priority in priorities:
                try:
                    db.session.add(priority)
                    db.session.commit()
                except:
                    db.session.rollback()
        return jsonify({'success': True, 'message': 'Database initialized successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.errorhandler(404)
def page_not_found(e):
    if request.path.startswith('/api'):
        return jsonify({'error': 'Not Found'}), 404
    return render_template('404.html', time=time), 404


@app.route('/get-saved-workouts', methods=['GET'])
def get_saved_workouts():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        saved_workouts = UserSavedWorkout.query.filter_by(user_id=session['user_id']).all()
        completed_workouts = set()
        for progress in UserWorkoutProgress.query.filter_by(user_id=session['user_id']).all():
            completed_workouts.add(progress.workout_id)
        workouts_list = []
        for saved in saved_workouts:
            w = Workout.query.get(saved.workout_id)
            if w:
                is_completed = (w.id in completed_workouts)
                workouts_list.append({
                    'id': w.id,
                    'title': w.title,
                    'description': w.description,
                    'duration': w.duration,
                    'difficulty': w.difficulty,
                    'video_url': w.video_url,
                    'saved_id': saved.id,
                    'scheduled_date': saved.scheduled_date.isoformat() if saved.scheduled_date else None,
                    'completed': is_completed
                })
        return jsonify({'workouts': workouts_list})
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/remove-workout', methods=['POST'])
def remove_workout():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        data = request.get_json()
        workout_id = data.get('workout_id')
        if not workout_id:
            return jsonify({'error': 'Workout ID is required'}), 400
        saved_workout = UserSavedWorkout.query.filter_by(
            user_id=session['user_id'],
            workout_id=workout_id
        ).first()
        if not saved_workout:
            return jsonify({'error': 'Workout not found in your plan'}), 404
        db.session.delete(saved_workout)
        db.session.commit()
        return jsonify({'message': 'Workout removed from your plan'})
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/clear-workout-plan', methods=['POST'])
def clear_workout_plan():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        UserSavedWorkout.query.filter_by(user_id=session['user_id']).delete()
        db.session.commit()
        return jsonify({'message': 'Workout plan cleared successfully'})
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/get-user-streak', methods=['GET'])
def get_user_streak():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        user_streak = UserStreak.query.filter_by(user_id=session['user_id']).first()
        if not user_streak:
            user_streak = UserStreak(
                user_id=session['user_id'],
                current_streak=1,
                longest_streak=1,
                last_login=date.today()
            )
            db.session.add(user_streak)
            db.session.commit()
        last_login_str = 'Today'
        if user_streak.last_login != date.today():
            last_login_str = user_streak.last_login.strftime('%b %d')
        return jsonify({
            'current': user_streak.current_streak,
            'longest': user_streak.longest_streak,
            'lastLogin': last_login_str
        })
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/update-streak', methods=['POST'])
def update_user_streak():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        streak = update_streak(session['user_id'])
        if streak:
            return jsonify({
                'message': 'Streak updated successfully',
                'streak': {
                    'current': streak.current_streak,
                    'longest': streak.longest_streak
                }
            })
        else:
            return jsonify({'message': 'Failed to update streak', 'streak': None})
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/get-scheduled-workouts', methods=['GET'])
def get_scheduled_workouts():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        saved_workouts = UserSavedWorkout.query.filter_by(user_id=session['user_id']).all()
        completed_workouts = set()
        for progress in UserWorkoutProgress.query.filter_by(user_id=session['user_id']).all():
            completed_workouts.add(progress.workout_id)
        workouts_list = []
        for saved in saved_workouts:
            w = Workout.query.get(saved.workout_id)
            if w:
                is_completed = (w.id in completed_workouts)
                workouts_list.append({
                    'id': w.id,
                    'title': w.title,
                    'description': w.description,
                    'duration': w.duration,
                    'difficulty': w.difficulty,
                    'video_url': w.video_url,
                    'saved_id': saved.id,
                    'scheduled_date': saved.scheduled_date.isoformat() if saved.scheduled_date else None,
                    'completed': is_completed
                })
        return jsonify({'workouts': workouts_list})
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/get-completed-workouts', methods=['GET'])
def get_completed_workouts():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())  # Monday as the start
        end_of_week = start_of_week + timedelta(days=6)
        start_datetime = datetime.datetime.combine(start_of_week, datetime.time.min)
        end_datetime = datetime.datetime.combine(end_of_week, datetime.time.max)
        progress = UserWorkoutProgress.query.filter(
            UserWorkoutProgress.user_id == session['user_id'],
            UserWorkoutProgress.completed_date >= start_datetime,
            UserWorkoutProgress.completed_date <= end_datetime
        ).all()
        workouts_list = []
        for p in progress:
            workouts_list.append({
                'id': p.workout.id,
                'title': p.workout.title,
                'completed_date': p.completed_date.strftime('%Y-%m-%d'),
                'duration': p.duration,
                'rating': p.rating,
                'intensity': p.intensity,
                'notes': p.notes
            })
        return jsonify({'completed_workouts': workouts_list})
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500



@app.route('/improve-workout', methods=['POST'])
def improve_workout():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        data = request.get_json()
        workout_id = data.get('workout_id')
        difficulty = data.get('difficulty')
        duration = data.get('duration')
        if not workout_id or not difficulty or not duration:
            return jsonify({'error': 'Missing required fields'}), 400
        saved_workout = UserSavedWorkout.query.filter_by(
            user_id=session['user_id'],
            workout_id=workout_id
        ).first()
        if not saved_workout:
            return jsonify({'error': 'Workout not found in your plan'}), 404
        original_workout = Workout.query.get(workout_id)
        if not original_workout:
            return jsonify({'error': 'Original workout not found'}), 404
        if difficulty != original_workout.difficulty:
            similar_workouts = Workout.query.filter(
                Workout.title.like(f"%{original_workout.title.split(' ')[0]}%"),
                Workout.difficulty == difficulty
            ).all()
            if similar_workouts:
                saved_workout.workout_id = similar_workouts[0].id
                db.session.commit()
                return jsonify({
                    'message': f'Workout difficulty improved to {difficulty}!',
                    'workout_id': similar_workouts[0].id
                })
            else:
                alternative_workouts = Workout.query.filter_by(difficulty=difficulty).all()
                if alternative_workouts:
                    saved_workout.workout_id = alternative_workouts[0].id
                    db.session.commit()
                    return jsonify({
                        'message': f'Workout changed to {alternative_workouts[0].title} ({difficulty})!',
                        'workout_id': alternative_workouts[0].id
                    })
        if int(duration) != original_workout.duration:
            similar_duration_workouts = Workout.query.filter(
                Workout.title.like(f"%{original_workout.title.split(' ')[0]}%"),
                Workout.difficulty == original_workout.difficulty,
                Workout.duration >= int(duration)
            ).all()
            if similar_duration_workouts:
                saved_workout.workout_id = similar_duration_workouts[0].id
                db.session.commit()
                return jsonify({
                    'message': f'Workout duration extended to {similar_duration_workouts[0].duration} minutes!',
                    'workout_id': similar_duration_workouts[0].id
                })
            else:
                original_workout.duration = int(duration)
                db.session.commit()
                return jsonify({
                    'message': f'Workout duration updated to {duration} minutes!',
                    'workout_id': original_workout.id
                })
        return jsonify({'message': 'No changes made to workout'})
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500


def init_dietary_tags():
    """Initialize dietary tags if they don't exist"""
    try:
        if DietaryTag.query.count() == 0:
            tags = [
                DietaryTag(name="Vegan"),
                DietaryTag(name="Vegetarian"),
                DietaryTag(name="Keto"),
                DietaryTag(name="Gluten-Free"),
                DietaryTag(name="High-Protein"),
                DietaryTag(name="Low-Carb"),
                DietaryTag(name="Dairy-Free"),
                DietaryTag(name="Nut-Free"),
                DietaryTag(name="Paleo"),
                DietaryTag(name="Mediterranean")
            ]
            db.session.add_all(tags)
            db.session.commit()

            try:
                diet_hp = Diet.query.filter(Diet.name.like('%High Protein%')).first()
                if diet_hp:
                    hp_tag = DietaryTag.query.filter_by(name="High-Protein").first()
                    if hp_tag and hp_tag not in diet_hp.tags:
                        diet_hp.tags.append(hp_tag)

                diet_cd = Diet.query.filter(Diet.name.like('%Calorie Deficit%')).first()
                if diet_cd:
                    keto_tag = DietaryTag.query.filter_by(name="Keto").first()
                    if keto_tag and keto_tag not in diet_cd.tags:
                        diet_cd.tags.append(keto_tag)

                diet_heart = Diet.query.filter(Diet.name.like('%Mediterranean%')).first()
                if diet_heart:
                    med_tag = DietaryTag.query.filter_by(name="Mediterranean").first()
                    if med_tag and med_tag not in diet_heart.tags:
                        diet_heart.tags.append(med_tag)

                db.session.commit()
            except Exception as e:
                print(f"Error associating tags with diets: {str(e)}")
                db.session.rollback()

            return True
        return False
    except Exception as e:
        db.session.rollback()
        print(f"Error initializing dietary tags: {str(e)}")
        return False


if __name__ == '__main__':
    try:
        with app.app_context():
            db.create_all()
            try:
                inspector = sqlalchemy_inspect(db.engine)
                tables = inspector.get_table_names()
                if 'health_condition' not in tables or not HealthCondition.query.first():
                    init_db()
                    print("Database initialized successfully!")
            except Exception as e:
                print(f"Error initializing database: {str(e)}")
        app.run(debug=True, host='127.0.0.1', port=5001, use_reloader=True)
    except Exception as e:
        print(f"⚠️ Unexpected error: {str(e)}")
