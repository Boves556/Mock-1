import os
import pandas as pd
import json
from flask import Flask, request, render_template, redirect, url_for, flash
import matplotlib.pyplot as plt

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SECRET_KEY'] = 'supersecretkey'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'csv', 'json'}

def load_data(filepath):
    if filepath.endswith('.csv'):
        try:
            data = pd.read_csv(filepath)
            data.rename(columns={data.columns[0]: 'timestamp'}, inplace=True)
            data['timestamp'] = pd.to_datetime(data['timestamp'])
        except Exception as e:
            print(f"Error loading CSV file: {e}")
            return None
    elif filepath.endswith('.json'):
        try:
            with open(filepath, 'r') as f:
                json_data = json.load(f)
                records = []
                for entry in json_data:
                    heartRateValues = entry.get('heartRateValues')
                    if heartRateValues:
                        for value in heartRateValues:
                            records.append({'timestamp': pd.to_datetime(value[0], unit='ms'), 'heartrate': value[1]})
                data = pd.DataFrame(records)
        except Exception as e:
            print(f"Error loading JSON file: {e}")
            return None
    else:
        data = None
    return data

def check_data_quality(data):
    if data is None or 'timestamp' not in data.columns or 'heartrate' not in data.columns:
        print("Missing required columns.")
        return False
    data.set_index('timestamp', inplace=True)
    resampled_data = data.resample('2T').mean()
    resampled_data = resampled_data.dropna()
    window_2h = resampled_data.rolling('2H').count()
    return any(window_2h['heartrate'] >= 60)

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            data = load_data(filepath)
            if data is None:
                flash('Failed to load data')
                return redirect(request.url)
            if check_data_quality(data):
                return redirect(url_for('show_latest_interval', filepath=filename))
            else:
                flash('Data quality is not sufficient')
                return redirect(request.url)
    return render_template('index.html')

@app.route('/data', methods=['GET'])
def list_intervals():
    uploaded_files = os.listdir(app.config['UPLOAD_FOLDER'])
    intervals = []
    for file in uploaded_files:
        data = load_data(os.path.join(app.config['UPLOAD_FOLDER'], file))
        if data is not None and check_data_quality(data):
            intervals.append(file)
    return render_template('data.html', intervals=intervals)

def extract_2h_interval(data):
    data.set_index('timestamp', inplace=True)
    resampled_data = data.resample('2T').mean()
    resampled_data = resampled_data.dropna()
    window_2h = resampled_data.rolling('2H').mean()
    latest_2h = window_2h.tail(1).index[0]
    start_time = latest_2h - pd.Timedelta(hours=2)
    end_time = latest_2h
    interval_data = resampled_data[start_time:end_time]
    return interval_data

def plot_heartrate(interval_data):
    plt.figure()
    interval_data['heartrate'].plot()
    plt.xlabel('Time')
    plt.ylabel('Heartrate')
    plt.title('Heartrate over 2 hours')
    plt.savefig('static/plot.png')

@app.route('/<filepath>', methods=['GET'])
def show_latest_interval(filepath):
    data = load_data(os.path.join(app.config['UPLOAD_FOLDER'], filepath))
    if data is None:
        flash('Failed to load data')
        return redirect(url_for('upload_file'))
    interval_data = extract_2h_interval(data)
    min_hr = interval_data['heartrate'].min()
    max_hr = interval_data['heartrate'].max()
    avg_hr = interval_data['heartrate'].mean()
    plot_heartrate(interval_data)
    return render_template('interval.html', min_hr=min_hr, max_hr=max_hr, avg_hr=avg_hr, plot_url=url_for('static', filename='plot.png'))

if __name__ == '__main__':
    app.run(debug=True)
