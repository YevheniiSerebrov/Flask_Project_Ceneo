# from app import app
from fileinput import filename
import mimetypes
from flask import Flask, render_template, request, send_file, url_for
import requests
from matplotlib import pyplot as plt
from bs4 import BeautifulSoup
from translate import Translator
import numpy as np
import pandas as pd
import json
import os

app = Flask(__name__)
def scrape_reviews(product_code):
    def get_element(dom_tree, selector = None, attribute = None, return_list = False):
        try:
            if return_list:
                return ", ".join([tag.text.strip() for tag in dom_tree.select(selector)])
            if attribute:
                if selector:
                    return dom_tree.select_one(selector)[attribute].strip()
                return dom_tree[attribute]
            return dom_tree.select_one(selector).text.strip()
        except (AttributeError,TypeError):
            return None

    def clean_text(text):
        return ' '.join(text.replace(r"\s", " ").split())

    selectors = {
        "opinion_id": [None, "data-entry-id"],
        "author": ["span.user-post__author-name"],
        "recommendation": ["span.user-post__author-recomendation > em"],
        "score": ["span.user-post__score-count"],
        "description": ["div.user-post__text"],
        "pros": ["div.review-feature__col:has( > div.review-feature__title--positives) > div.review-feature__item", None, True],
        "cons": ["div.review-feature__col:has( > div.review-feature__title--negatives) > div.review-feature__item", None, True],
        "like": ["button.vote-yes > span"],
        "dislike": ["button.vote-no > span"],
        "publish_date": ["span.user-post__published > time:nth-child(1)","datetime"],
        "purchase_date": ["span.user-post__published > time:nth-child(2)","datetime"]
    }

    from_lang = "pl"
    to_lang = "en"
    translator = Translator(to_lang, from_lang)

    headers = {
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
    }
    url = f"https://www.ceneo.pl/{product_code}#tab=reviews"
    all_opinions = []
    while url:
        print(url)
        response = requests.get(url, headers=headers)   #?
        if  response.status_code == requests.codes.ok:
            page_dom = BeautifulSoup(response.text, "html.parser")
            opinions = page_dom.select("div.js_product-review")
            # image_element = page_dom.find('img', class_='js_gallery-media gallery-carousel__media lazyloaded')
            # image_url = image_element['src']
            for opinion in opinions:
                single_opinion = {}
                for key, value in selectors.items():
                    single_opinion[key] = get_element(opinion, *value)
                single_opinion["recommendation"] = True if single_opinion["recommendation"] == "Polecam" else False if single_opinion["recommendation"] == "Nie polecam" else None
                single_opinion["score"] = np.divide(*[float(score.replace(",", ".")) for score in single_opinion["score"].split("/")])
                single_opinion["like"] = int(single_opinion["like"])
                single_opinion["dislike"] = int(single_opinion["dislike"])
                single_opinion["description"] = clean_text(single_opinion["description"])
                single_opinion["description_en"] = translator.translate(single_opinion["description"][:500])
                single_opinion["pros_en"] = translator.translate(single_opinion["pros"][:500])
                single_opinion["cons_en"] = translator.translate(single_opinion["cons"][:500])
                all_opinions.append(single_opinion)
            
            try:
                page = get_element(page_dom, "a.pagination__next","href")
                url = "https://www.ceneo.pl" + page
            except TypeError:
                url = None
    
    return all_opinions

@app.route("/", methods=["GET", "POST"])

def index():
    if request.method == "POST":
        product_code = request.form["product_code"]
        reviews = scrape_reviews(product_code)
        if len(reviews) > 0:
            if not os.path.exists("./opinions"):
                os.mkdir("./opinions")
            with open(f"./opinions/{product_code}.json", "w",encoding="UTF-8") as jf:
                json.dump(reviews,jf,indent=4,ensure_ascii=False)
        print(*[filename.split(".")[0] for filename in os.listdir("./opinions")], sep="\n")

        opinions = pd.read_json(f"./opinions/{product_code}.json")

        max_score = 5

        opinions['stars'] = (opinions['score']*max_score).round(1)

        opinions_count = opinions.shape[0]
        pros_count = opinions.pros.astype(bool).sum()
        cons_count = opinions.cons.astype(bool).sum()
        average_score = round((opinions.stars.mean()),2)

        final_text = (f"""For the product with the {product_code} code
        there is {opinions_count} opinions posted.
        For {pros_count} opinions the list of product advantages is given
        and for {cons_count} opnions the list of product disadvantages is given.
        The average score for product is {average_score}.""")

        if not os.path.exists('app/charts'):
            os.mkdir('app/charts')

        recommendations = opinions.recommendation.value_counts(dropna=False).reindex([True,False,np.nan], fill_value=0)

        recommendations.plot.pie(
            label="",
            labels = ["Recommend", "Not recommend", "Neutral"],
            colors = ["dodgerblue", "orangered","slategray"],
            autopct = lambda p: '{:.1f}%'.format(round(p)) if p > 0 else ''
        )
        plt.title("Recommendations")
        plt.savefig(f"app/static/{product_code}_pie.webp")
        plt.close()
        stars = opinions.stars.value_counts().reindex(list(np.arange(0,5.5,0.5)), fill_value=0)

        stars.plot.bar(color="cornflowerblue")
        plt.ylim(0,max(stars)+10)
        plt.title("Star count distribution")
        plt.xlabel("Number of stars")
        plt.ylabel("Number of opinions")
        plt.xticks(rotation = 0)
        plt.grid(True, "major", "y")
        for index, value in enumerate(stars):
            plt.text(index, value+1.5, str(value), ha = 'center')
        plt.savefig(f"app/static/{product_code}_plot.webp")
        return render_template('results.html', final_text=final_text, reviews=reviews, product_code=product_code)
    return render_template('index.html')


if __name__ == "__main__":
    app.run(debug=True)