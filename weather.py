# What's the Weather?
# If you would like to know the basics of what an API is, check out this post by iamapizza.
#
# Create a program that pulls data from OpenWeatherMap.org and prints out information about the current weather,
# such as the high, the low, and the amount of rain for wherever you live.

# Subgoals: Print out data for the next 5-7 days so you have a 5 day/week long forecast.
# Print the data to another file that you can open up and view at,
# instead of viewing the information in the command line.
# If you know html, write a file that you can print information to so that your project is more interesting.
# Here is an example of the results from what I threw together.[3]
#
# Tips: APIs that are in Json are essentially lists and dictionaries. Remember that to reference
# something in a list, you must refer to it by what number element it is in the list, and to reference a key in a
# dictionary, you must refer to it by it's name.

import requests
from flask import Flask, render_template, request
import flask_session
import json
import werkzeug.exceptions
import datetime
import pygal
from pygal.style import Style
import dont_include

# import key data and set as global vars from alternate file for safety purposes
KEY = dont_include.KEY
ROLLESTON_CODE = dont_include.ROLLESTON_CODE
URL = dont_include.URL

# api.openweathermap.org/data/2.5/forecast?id={2183310}&appid={0e94bd373c11928545ae49efdbda3463} - 5 day

# Configure application and ensure templates are auto-reloaded
app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached - CODE FROM CS50, may not need

# @app.after_request
# def after_request(response):
#     response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
#     response.headers["Expires"] = 0
#     response.headers["Pragma"] = "no-cache"
#     return response


def write_json(data):
    file = open("rolleston_weather.json", "w")
    file.write(str(data))
    file.close()
    return data


def convert_unix(sent_time, timezone):
    time_str = datetime.datetime.utcfromtimestamp(int(sent_time + timezone)).strftime('%d %b %H:%M')
    return time_str


def format_data(data):
    timezone = data['city']['timezone']
    head_data = {
        'city': data['city']['name'],
        'coord': (data['city']['coord']['lat'], data['city']['coord']['lon']),
        'country': data['city']['country'],
        'timezone': timezone,
        'sunrise': convert_unix(data['city']['sunrise'], timezone),
        'sunset': convert_unix(data['city']['sunset'], timezone),
        'get_time': datetime.datetime.now().strftime('%d-%b %H:%M')
    }
    daily_data = {}
    for i in range(int(data['cnt']) - 16):
        time = convert_unix(data['list'][i]['dt'], timezone)
        new_dict = {
            'temp': data['list'][i]['main']['temp'],
            'feels_like': data['list'][i]['main']['feels_like'],
            'humidity': data['list'][i]['main']['humidity'],
            'weather': data['list'][i]['weather'][0]['main'],
            'weather_desc': data['list'][i]['weather'][0]['description'].capitalize(),
            'icon': "https://openweathermap.org/img/w/" + data['list'][i]['weather'][0]['icon'] + ".png"
        }
        daily_data[time] = new_dict
    return head_data, daily_data


def draw_temp_graph(head, daily):
    x_axis = []
    y_actual = []
    y_feels = []
    for day, data in daily.items():
        x_axis.append(day)
        y_actual.append(data['temp'])
        y_feels.append(data['feels_like'])
    title = "3-day weather forecast for " + head['city'] + ", " + head['country']
    # Setup styling of graph
    graph_style = Style(
        background='transparent',
        opacity='.7',
        opacity_hover='.9',
        transition='200ms ease-in',
        colors=('#e07da6', '#7da6e0'),
        font_family='googlefont:Roboto',
        title_font_size=20
    )
    # Create chart using the above data
    line_graph = pygal.Line(
        x_label_rotation=70,
        fill=True,
        interpolate='cubic',
        style=graph_style,
        y_title='(°C)'
    )
    line_graph.title = title
    line_graph.x_labels = x_axis
    line_graph.add('Temperature', y_actual)
    line_graph.add('Feels like', y_feels)
    line_graph.render_to_file('chart.svg')
    return line_graph


@app.route("/")
def index():
    api = requests.get(URL).json()
    data = write_json(api)
    head_data, daily_data = format_data(data)
    line_graph = draw_temp_graph(head_data, daily_data)
    chart = line_graph.render_data_uri()
    return render_template('index.html', chart=chart)


# todo add more stuff to the flask site


if __name__ == '__main__':
    app.run()
