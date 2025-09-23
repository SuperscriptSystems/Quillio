from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, IntegerField, RadioField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')


class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')


class VerificationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    verification_code = StringField('Verification Code', validators=[DataRequired()])
    submit = SubmitField('Verify')

class InitialAssessmentForm(FlaskForm):
    topic = StringField("Topic", validators=[DataRequired()])
    knowledge = IntegerField("Knowledge", validators=[DataRequired()])
    submit = SubmitField("Start Assessment")

class AnswerForm(FlaskForm):
    answer = RadioField("Answer", choices=[], validators=[DataRequired()])
    submit = SubmitField("Next")

