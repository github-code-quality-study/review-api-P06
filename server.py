import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from nltk.corpus import stopwords
from urllib.parse import parse_qs, urlparse
import json
import pandas as pd
from datetime import datetime
import uuid
import os
from typing import Callable, Any
from wsgiref.simple_server import make_server
import re

nltk.download('vader_lexicon', quiet=True)
nltk.download('punkt', quiet=True)
nltk.download('averaged_perceptron_tagger', quiet=True)
nltk.download('stopwords', quiet=True)

adj_noun_pairs_count = {}
sia = SentimentIntensityAnalyzer()
stop_words = set(stopwords.words('english'))

reviews = pd.read_csv('data/reviews.csv').to_dict('records')
valid_locations = set(review['Location'] for review in reviews if 'Location' in review)

class ReviewAnalyzerServer:
    def __init__(self) -> None:
        # This method is a placeholder for future initialization logic
        pass

    def filter_reviews(self,loc=None,start_date=None,end_date=None):
        filtered_result = reviews
        if loc:
            filtered_result = [review for review in filtered_result if review['Location'] == loc]
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            filtered_result = [
                review for review in filtered_result
                if datetime.strptime(review['Timestamp'].split(' ')[0], '%Y-%m-%d') >= start_date
            ]
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
            filtered_result = [
                review for review in filtered_result
                if datetime.strptime(review['Timestamp'].split(' ')[0], '%Y-%m-%d') <= end_date
            ]
        return filtered_result

    def analyze_sentiment(self, review_body):
        sentiment_scores = sia.polarity_scores(review_body)
        return sentiment_scores

    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]) -> bytes:
        """
        The environ parameter is a dictionary containing some useful
        HTTP request information such as: REQUEST_METHOD, CONTENT_LENGTH, QUERY_STRING,
        PATH_INFO, CONTENT_TYPE, etc.
        """
        # print("printing environ", environ)
        if environ["REQUEST_METHOD"] == "GET":
            # Create the response body from the reviews and convert to a JSON byte string
            ## response_body = json.dumps(reviews, indent=2).encode("utf-8")
            
            # Write your code here
            query_param = parse_qs(urlparse(environ['QUERY_STRING']).path)

            # Get Location
            loc = query_param.get('location',[None])[0]

            # Get (start date and end date) for filtering timestamp
            start_date = query_param.get('start_date',[None])[0]
            end_date = query_param.get('end_date',[None])[0]

            print("Printing params:",query_param,loc,start_date,end_date)

            # Filter by location and timestamp
            filtered_reviews = self.filter_reviews(loc, start_date, end_date)

            results = []
            for review in filtered_reviews:
                sentiment = self.analyze_sentiment(review['ReviewBody'])
                results.append({
                    'ReviewId': review['ReviewId'],
                    'ReviewBody': review['ReviewBody'],
                    'Location': review['Location'],
                    'Timestamp': review['Timestamp'],
                    'sentiment': sentiment
                })

            results.sort(key=lambda x: x['sentiment']['compound'], reverse=True)

            response_body = json.dumps(results, indent=2).encode("utf-8")
            
            # Set the appropriate response headers
            start_response("200 OK", [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(response_body)))
             ])
            
            return [response_body]


        if environ["REQUEST_METHOD"] == "POST":
            # Write your code here
            content_length = int(environ.get('CONTENT_LENGTH', 0))
            post_data = environ['wsgi.input'].read(content_length)
            post_data = parse_qs(post_data.decode('utf-8'))

            print("Printing post data",post_data)

            review_body = post_data.get('ReviewBody', [None])[0]
            loc = post_data.get('Location', [None])[0]

            if loc not in valid_locations:
                start_response("400 Bad Request", [
                    ("Content-Type", "application/json"),
                    ("Content-Length", "0")
                ])
                return []

            if not review_body:
                start_response("400 Bad Request", [
                    ("Content-Type", "application/json"),
                    ("Content-Length", "0")
                ])
                return []

            new_review = {
                'ReviewId': str(uuid.uuid4()),
                'ReviewBody': review_body,
                'Location': loc,
                'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            reviews.append(new_review)
            valid_locations.add(loc)

            response_body = json.dumps(new_review, indent=2).encode("utf-8")

            start_response("201 Created", [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(response_body)))
            ])

            return [response_body]

if __name__ == "__main__":
    app = ReviewAnalyzerServer()
    port = os.environ.get('PORT', 8000)
    with make_server("", port, app) as httpd:
        print(f"Listening on port {port}...")
        httpd.serve_forever()