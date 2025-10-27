# Version 2.0
# Credits MyDealz @Barney & @Gorex 

import requests
import geopy.distance
import tempfile
import webbrowser
import concurrent.futures
import json
import time

DEBUG = False
AUTO_OPEN_BROWSER = True
LOGO = r'''
                           _     _____ _               _             
                          | |   /  __ \ |             | |            
  _____  ___ __   ___ _ __| |_  | /  \/ |__   ___  ___| | _____ _ __ 
 / _ \ \/ / '_ \ / _ \ '__| __| | |   | '_ \ / _ \/ __| |/ / _ \ '__|
|  __/>  <| |_) |  __/ |  | |_  | \__/\ | | |  __/ (__|   <  __/ |   
 \___/_/\_\ .__/ \___|_|   \__|  \____/_| |_|\___|\___|_|\_\___|_|   
          | |                                                        
          |_|                                                        
'''

headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
    }

def get_article_id(url):
    """Liefert für URL die interne Artikelnummer eines Produkts."""
    webcode = url.split("/")[-1].split("-")[0]
    params = {
        'webcode': webcode,
        'storeId': 'e_2879130',
    }
    response = requests.get('https://production.brntgs.expert.de/api/pricepds', params=params, headers=headers)
    data = response.json()
    articleId = data["articleId"]
    if DEBUG:
        print(f"Artikelnummer: {articleId}")
    return articleId


def get_article_id_from_search(search_term):
    """Liefert für Suchbegriff die interne Artikelnummer eines Produkts aus der Suche (unzuverlässig)."""
    params = {
        'q': search_term,
        'storeId': 'e_2879130',
    }
    response = requests.get('https://production.brntgs.expert.de/api/search/suggest', params=params, headers=headers)
    try:
        product_data = response.json()["articleSuggest"]
        if len(product_data) == 0:
            return 0
        for product in product_data:
            counter = product_data.index(product) + 1
            title = product["article"]["seoPageTitle"].split(" - bei expert kaufen")[0]
            print(f"{counter}) {title}")
        choice = int(input("Bitte Produktauswahl treffen: "))
        articleId = product_data[choice - 1]["article"]["articleId"]
        url = "https://www.expert.de/shop/unsere-produkte/" + product_data[choice - 1]["article"]["slug"]
        return articleId, url
    except:
        return 0


def get_branches():
    """Ruft die Liste aller Filialen direkt von expert ab oder weicht bei Fehler auf Alternative aus."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0',
    }
    params = {
        "lat": 0,
        "lng": 0,
        "maxResults": 500,
        "device": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
        "source": "HTML5",
        "withWebsite": True,
        "conditions": {
            "storeFinderResultFilter": "ALL"}
    }

    cookies = {
        'fmarktcookie': 'e_2879130'
    }

    try:
        response = requests.post(
            'https://production.brntgs.expert.de/_api/storeFinder/searchStoresByGeoLocation',
            headers=headers,
            json=params,
            cookies=cookies,
        )
        branches = response.json()
    except:
        if DEBUG:
            print("Filialabruf direkt von expert nicht möglich. Nutze lokales Backup.")
        with open('expert_branches.json', 'r') as f:
            branches = json.loads(f.read())
    return branches

def get_branch_product_data(webcode, storeid):
    """Liefert API-Daten (Preis, Verfügbarkeit, etc.) eines Produkts für eine Filiale."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
        'Accept': 'application/json',
        'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
    }
    params = {
        'webcode': webcode,
        'storeId': storeid,
    }
    
    max_retries = 5  # Maximale Anzahl von Wiederholungsversuchen
    retry_delay = 2  # Wartezeit zwischen Versuchen in Sekunden
    
    for attempt in range(max_retries):
        try:
            response = requests.get(
                'https://production.brntgs.expert.de/api/pricepds',
                headers=headers,
                params=params,
            )
            
            if response.status_code == 429:
                if DEBUG:
                    print(f"\nRate limit erreicht für Filiale {storeid}. Warte {retry_delay} Sekunden...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponentielles Backoff
                continue
                
            response.raise_for_status()  # Wirft eine Exception für andere Fehlercodes
            return response.json()
            
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:  # Letzter Versuch
                if DEBUG:
                    print(f"\nFehler bei Filiale {storeid} nach {max_retries} Versuchen: {str(e)}")
                raise
            if DEBUG:
                print(f"\nFehler bei Filiale {storeid}, versuche erneut...")
            time.sleep(retry_delay)
            retry_delay *= 2  # Exponentielles Backoff
            continue


def get_coordinates(plz):
    """Liefert für PLZ die zugehörigen Geo-Koordinaten."""
    try:
        # Entferne eventuelle Leerzeichen und stelle sicher, dass es 5 Ziffern sind
        plz = plz.strip()
        if not plz.isdigit() or len(plz) != 5:
            if DEBUG:
                print(f"Ungültige PLZ: {plz}")
            return None

        response = requests.get(f"https://api.zippopotam.us/de/{plz}")
        if response.status_code != 200:
            if DEBUG:
                print(f"Fehler beim Abrufen der Koordinaten: Status {response.status_code}")
            return None

        data = response.json()

        # Überprüfe, ob 'places' existiert und nicht leer ist
        if "places" not in data or not data["places"]:
            if DEBUG:
                print(f"Keine Koordinaten in der Antwort gefunden: {data}")
            return None

        # Zugriff auf das erste Element im 'places'-Array
        place = data["places"][0]
        coordinates = (
            float(place["latitude"]),
            float(place["longitude"])
        )
        
        if DEBUG:
            print(f"Koordinaten für PLZ {plz}: {coordinates}")
        return coordinates

    except Exception as e:
        if DEBUG:
            print(f"Fehler beim Abrufen der Koordinaten: {str(e)}")
        return None


def get_discount(articleId):
    """Liefert einen eventuellen Direktabzug (alternativ Wert 0)."""
    total_discount = 0
    # API-Anfrage an expert für aktive Promotionen
    response = requests.get("https://production.brntgs.expert.de/api/activePromotions", headers=headers)
    promotions = response.json()
    
    # Jede Promotion wird überprüft
    for promotion in promotions:
        # Liste der Artikel, für die die Promotion gilt
        affectedArticles = promotion["orderModification"][0]["affectedArticles"]
        
        # Prüfen ob der gesuchte Artikel in der Liste ist
        if articleId in affectedArticles:
            try:
                title = promotion["title"]
                # Rabattbetrag aus der Promotion extrahieren
                discount = promotion["orderModification"][0]["discountRanges"][0]["discount"]
                if DEBUG:
                    print(f"{title}: {discount}€ Rabatt")
                total_discount += discount
            except KeyError:
                pass
                
    if DEBUG:
        if total_discount == 0:
            print("Es gibt keinen Direktabzug.")
        else:
            print(f"{total_discount}€ Direktabzug gefunden.")
            
    return total_discount



def get_distance(coords1, coords2):
    """Liefert die Distanz zwischen zwei Koordinaten, gerundet auf volle Kilometer."""
    distance = geopy.distance.geodesic(coords1, coords2).km
    return int(round(distance, 0))


def format_price(number, is_shipping=False, has_online_stock=False):
    """ Zahl rein, korrekt formatierter Preis raus. """
    # Bei Versandkosten: Leerer String wenn kein Online-Versand möglich
    if is_shipping and not has_online_stock:
        return ""
    # Bei 0 und Online-Versand möglich: "0,00€" anzeigen
    if number == 0:
        return "0,00€"
    # Formatiere die Zahl mit zwei Dezimalstellen
    price = f"{number:.2f}€"
    # Ersetze den Punkt durch ein Komma
    price = price.replace(".", ",")
    return price


def create_html_report(offers, product_title, webcode, discount):
    # Finde die besten Preise für neue und Ausstellungsstücke
    best_new_price = None
    best_display_price = None
    
    for offer in offers:
        if offer['online_stock'] > 0:  # Nur versandfähige Artikel
            if offer['on_display']:
                if best_display_price is None or offer['total_price'] < best_display_price['total_price']:
                    best_display_price = offer
            else:
                if best_new_price is None or offer['total_price'] < best_new_price['total_price']:
                    best_new_price = offer

    html_content = f'''
    <html>
    <head>
        <meta charset="UTF-8">
        <title>expert checker reborn</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f5f5f5;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
            }}
            h1, h2 {{
                text-align: center;
                color: #333;
                margin-bottom: 30px;
            }}
            .product-info {{
                text-align: center;
                margin-bottom: 30px;
                color: #666;
            }}
            .product-title {{
                font-size: 1.2em;
                margin-bottom: 10px;
            }}
            .discount-info {{
                color: #28a745;
                font-weight: 600;
                margin-bottom: 15px;
            }}
            .best-price-info {{
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 30px;
                text-align: center;
            }}
            .best-price-item {{
                margin: 10px 0;
                font-size: 1.1em;
            }}
            .best-price-item a {{
                color: #0066cc;
                text-decoration: none;
                font-weight: 600;
            }}
            .best-price-item a:hover {{
                text-decoration: underline;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                background-color: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                margin-bottom: 30px;
            }}
            th, td {{
                padding: 12px 15px;
                text-align: left;
                border-bottom: 1px solid #eee;
            }}
            th {{
                background-color: #f8f9fa;
                font-weight: 600;
                color: #333;
            }}
            tr:hover {{
                background-color: #f8f9fa;
            }}
            a {{
                color: #0066cc;
                text-decoration: none;
            }}
            a:hover {{
                text-decoration: underline;
            }}
            .price {{
                font-weight: 600;
                color: #333;
            }}
            .shipping {{
                color: #666;
            }}
            .total-price {{
                font-weight: 700;
                color: #0066cc;
            }}
            .availability {{
                color: #666;
                font-size: 0.9em;
            }}
            .online {{
                color: #28a745;
            }}
            .offline {{
                color: #dc3545;
            }}
            .display-item {{
                background-color: #fff3cd;
            }}
            .display-item:hover {{
                background-color: #ffe7b3;
            }}
            .collapsible {{
                background-color: #f8f9fa;
                color: #333;
                cursor: pointer;
                padding: 18px;
                width: 100%;
                border: none;
                text-align: left;
                outline: none;
                font-size: 1.1em;
                font-weight: 600;
                border-radius: 8px;
                margin-bottom: 5px;
            }}
            .active, .collapsible:hover {{
                background-color: #e9ecef;
            }}
            .content {{
                max-height: 0;
                overflow: hidden;
                transition: max-height 0.2s ease-out;
                background-color: white;
                border-radius: 0 0 8px 8px;
            }}
            .collapsible:after {{
                content: '\\002B';
                color: #666;
                font-weight: bold;
                float: right;
                margin-left: 5px;
            }}
            .active:after {{
                content: "\\2212";
            }}
        </style>
        <script>
            function toggleCollapsible(element) {{
                element.classList.toggle("active");
                var content = element.nextElementSibling;
                if (content.style.maxHeight) {{
                    content.style.maxHeight = null;
                }} else {{
                    content.style.maxHeight = content.scrollHeight + "px";
                }}
            }}
        </script>
    </head>
    <body>
        <div class="container">
        <h1>expert checker reborn</h1>
            <div class="product-info">
                <div class="product-title">{product_title} (Webcode: {webcode})</div>
                <div class="discount-info">Direktabzug: {format_price(discount) if discount > 0 else "-"}</div>
                <div class="best-price-info">
    '''
    
    if best_new_price:
        html_content += f'''
                    <div class="best-price-item">
                        Gesamtpreis: {format_price(best_new_price['total_price'])} bei <a href="{best_new_price['url']}" target="_blank">{best_new_price['store_name']}</a>
                    </div>
        '''
    
    if best_display_price:
        html_content += f'''
                    <div class="best-price-item">
                        Ausstellungsstück: {format_price(best_display_price['total_price'])} bei <a href="{best_display_price['url']}" target="_blank">expert {best_display_price['store_name']}</a>
                    </div>
        '''
    
    html_content += '''
                </div>
            </div>
            <button class="collapsible" onclick="toggleCollapsible(this)">Angebote anzeigen</button>
            <div class="content">
                <table>
                    <tr>
                        <th>Filiale</th>
                        <th>Preis</th>
                        <th>Versand</th>
                        <th>Gesamtpreis</th>
                        <th>Verfügbarkeit</th>
                    </tr>
    '''
    for offer in offers:
        if offer['online_stock'] == 0:
            availability = f'<span class="offline">Nur lokal verfügbar ({offer["stock"]}x)</span>'
        else:
            availability = f'<span class="online">Online verfügbar ({offer["online_stock"]}x)</span>'
            if offer['stock'] > 0:
                availability += f'<br><span class="offline">Lokal verfügbar ({offer["stock"]}x)</span>'
                
        display_class = ' class="display-item"' if offer["on_display"] else ''
        html_content += f'''
                    <tr{display_class}>
                        <td><a href="{offer['url']}" target="_blank">{offer['store_name']}</a></td>
                        <td class="price">{format_price(offer['price'])}</td>
                        <td class="shipping">{format_price(offer['shipping'], is_shipping=True, has_online_stock=offer['online_stock'] > 0)}</td>
                        <td class="total-price">{format_price(offer['total_price'])}</td>
                        <td class="availability">{availability}</td>
                    </tr>
        '''
    
    html_content += '''
                </table>
            </div>
            <button class="collapsible" onclick="toggleCollapsible(this)">Alle durchsuchten Filialen anzeigen</button>
            <div class="content">
                <table>
                    <tr>
                        <th>Filiale</th>
                        <th>Branch ID</th>
                        <th>Expert ID</th>
                    </tr>
    '''
    
    for branch in branches:
        html_content += f'''
                    <tr>
                        <td>{branch['store']['name']} {branch['store']['city']}</td>
                        <td>{branch['store']['id']}</td>
                        <td>{branch['store']['expId']}</td>
                    </tr>
        '''

    html_content += '''
                </table>
            </div>
        </div>
    </body>
    </html>
    '''
    with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as f:
        f.write(html_content.encode('utf-8'))
        return f.name


print(LOGO)

def get_article_id_from_id(article_id):
    """Liefert für eine Artikelnummer die zugehörigen Produktdaten."""
    try:
        if DEBUG:
            print(f"Suche Produkt mit Artikelnummer: {article_id}")
            
        # Zuerst die ArticleId in einen Webcode umwandeln
        response = requests.get(
            f"https://production.brntgs.expert.de/api/pricepds",
            params={'articleId': article_id, 'storeId': 'e_2879130'},
            headers=headers
        )
        
        if DEBUG:
            print(f"API Status Code: {response.status_code}")
            
        if response.status_code != 200:
            if DEBUG:
                print(f"API Fehler: {response.status_code}")
            return 0
            
        data = response.json()
        
        if DEBUG:
            print(f"API Antwort: {data}")
        
        if not data or not data.get("webcode"):
            if DEBUG:
                print("Kein Webcode in der API-Antwort gefunden")
            return 0
            
        # Mit dem Webcode die vollständigen Produktdaten abrufen
        webcode = data["webcode"]
        title_response = requests.get(
            f"https://production.brntgs.expert.de/api/search/article?webcode={webcode}",
            headers=headers
        )
        
        if title_response.status_code != 200:
            if DEBUG:
                print(f"API Fehler beim Abrufen der Produktdaten: {title_response.status_code}")
            return 0
            
        title_data = title_response.json()
        
        if not title_data or not title_data.get("slug"):
            if DEBUG:
                print("Keine Produktdaten in der API-Antwort gefunden")
            return 0
            
        article = title_data
        
        # Baue die vollständige URL
        if article.get("slug"):
            url = f"https://www.expert.de/shop/unsere-produkte/{article['slug']}"
        else:
            if DEBUG:
                print("Kein Slug für die URL-Konstruktion gefunden")
            return 0
        
        if DEBUG:
            print(f"Produkt gefunden: {article.get('title', 'Kein Titel')}")
            print(f"Webcode: {webcode}")
            print(f"URL: {url}")
            
        return article_id, url
    except requests.exceptions.RequestException as e:
        if DEBUG:
            print(f"Netzwerkfehler beim Abrufen der Produktdaten: {str(e)}")
        return 0
    except json.JSONDecodeError as e:
        if DEBUG:
            print(f"Fehler beim Dekodieren der API-Antwort: {str(e)}")
        return 0
    except Exception as e:
        if DEBUG:
            print(f"Unerwarteter Fehler: {str(e)}")
        return 0

# URL checken und eventuelle Parameter entfernen
while True:
    term = input("Bitte Produkt-URL von expert, Artikelnummer oder Suchbegriff eingeben: ")
    
    # Prüfe ob es eine Artikelnummer ist (nur Zahlen)
    if term.isdigit():
        article_data = get_article_id_from_id(term)
        if article_data != 0:
            articleId = article_data[0]
            url = article_data[1]
            # Hole die korrekte ArticleId für Direktabzüge
            webcode = url.split("/")[-1].split("-")[0]
            articleId = get_article_id(url)
            break
        else:
            print("Keine gültige Artikelnummer. Bitte erneut versuchen.")
    # Prüfe ob es eine URL ist
    elif "www.expert.de" in term and ".html" in term:
        url = term.split(".html")[0] + ".html"
        print("Rufe Artikeldaten ab...")
        articleId = get_article_id(url)
        break
    # Ansonsten als Suchbegriff behandeln
    else:
        article_data = get_article_id_from_search(term)
        if article_data != 0:
            articleId = article_data[0]
            url = article_data[1]
            break
        else:
            print("Da stimmt irgendwas nicht. Bitte erneut versuchen.")

# Optionale Filteroptionen
only_new_items = input("Sollen auch Ausstellungsstücke angezeigt werden? (j/n): ").lower() != "j"
only_online_offers = input("Sollen auch lokale Angebote angezeigt werden? (j/n): ").lower() != "j"

# Optionale Eingabe von Postleitzahl und Distanz
if not only_online_offers:
    while True:
        plz = input("Deine Postleitzahl eingeben: ")
        user_coordinates = get_coordinates(plz)
        if user_coordinates is None:
            print("Ungültige PLZ oder Fehler beim Abrufen der Koordinaten. Bitte erneut versuchen.")
            continue
        
        try:
            max_distance_input = input("Maximale Distanz für lokale Angebote in km eingeben (leer = unbegrenzt): ")
            max_distance = int(max_distance_input) if max_distance_input.strip() else 999999
            if max_distance <= 0:
                print("Die Distanz muss größer als 0 sein.")
                continue
            break
        except ValueError:
            print("Bitte eine gültige Zahl eingeben.")
            continue

# Filialen, Artikeldaten und eventuelle Direktabzüge abrufen
print("Rufe Filialen ab...")
branches = get_branches()

print("Suche nach Direktabzügen...")
discount = get_discount(articleId)

# Leere Liste für spätere Verwendung
all_offers = []

def process_branch(branch):
    # Programmiertechnisch unsauberer Try-Block, damit das Programm bei Fehlern einzelner Filialen nicht komplett abstürzt
    try:
        branch_id = branch["store"]["id"]
        expert_id = branch["store"]["expId"]
        branch_name = branch["store"]["name"]
        branch_city = branch["store"]["city"]
        branch_coordinates = (branch["store"]["latitude"], branch["store"]["longitude"])
        if branch_city not in branch_name:
            branch_name = f"{branch_name} {branch_city}"
        final_url = f"{url}?branch_id={branch_id}"
        if DEBUG:
            print(f"Filiale {branches.index(branch) + 1}/{len(branches)}: {final_url}")
        else:
            print(f"\rFiliale {branches.index(branch) + 1}/{len(branches)}", end="")

        # Extrahiere den Webcode aus der URL
        webcode = url.split("/")[-1].split("-")[0]

        # Produktdaten abrufen und Zustand prüfen
        product_data = get_branch_product_data(webcode, storeid=expert_id)
        if DEBUG:
            print(product_data)
        item_is_used = product_data["price"]["itemOnDisplay"]["onDisplay"] if product_data.get("price", {}).get("itemOnDisplay") else False

        # Abfrage bei Nichtverfügbarkeit abbrechen
        if not product_data.get("price", {}).get("bruttoPrice"):
            if DEBUG:
                print("Nicht verfügbar.")
            return

        # Offline-Angebote optional rausfiltern
        if only_online_offers and not product_data["price"].get("onlineStock", 0):
            if DEBUG:
                print("Nicht online bestellbar.")
            return

        # Zu weit entfernte Offline-Angebote optional rausfiltern
        if not only_online_offers and not product_data["price"].get("onlineStock", 0):
            distance = get_distance(user_coordinates, branch_coordinates)
            if distance > max_distance:
                if DEBUG:
                    print("Zu weit entfernt.")
                return

        # Ausstellungsstücke optional rausfiltern
        if only_new_items and item_is_used:
            if DEBUG:
                print("Nur Ausstellungsstück.")
            return

        # Preis, Versand und Gesamtpreis berechnen
        promotion_info = product_data.get("promotionPrice")
        price = round(float(promotion_info.get("checkoutPrice")), 2)
        
        # Versandkosten nur bei Online-Verfügbarkeit
        if product_data["price"].get("onlineStock", 0) > 0:
            shipping = round(float(product_data["price"]["shipmentArray"][0]["shipmentBruttoPrice"]), 2)
        else:
            shipping = 0
            
        total_price = round(price + shipping, 2)

        # Lokale Daten in Gesamtliste einfügen
        branch_offer = {
            "url": final_url,
            "price": price,
            "shipping": shipping,
            "total_price": total_price,
            "store": expert_id,
            "store_name": branch_name,
            "stock": product_data["price"].get("storeStock", 0),
            "online_store": product_data["price"].get("onlineStore", False),
            "online_stock": product_data["price"].get("onlineStock", 0),
            "on_display": item_is_used,
            "coordinates": branch_coordinates,
        }
        return branch_offer
    except:
        pass

# Produktabfrage für alle Filialen parallel
with concurrent.futures.ThreadPoolExecutor() as executor:
    results = list(executor.map(process_branch, branches))

# Ergebnisse filtern und sortieren
all_offers = [offer for offer in results if offer]
all_offers = sorted(all_offers, key=lambda d: d['store_name'])
all_offers = sorted(all_offers, key=lambda d: d['total_price'])

# Kurze Zusammenfassung ausgeben
if len(all_offers) > 0:
    print(f"\n{len(all_offers)} Angebote gefunden. Details werden im Browser angezeigt.")
else:
    print("\nEs wurden keine Angebote gefunden.")

if AUTO_OPEN_BROWSER or input('\nErgebnis im Browser ansehen?  (j/n): ').lower() == 'j':
    # Extrahiere den Webcode aus der URL
    webcode = url.split("/")[-1].split("-")[0]
    # Hole den Produkttitel von der API
    title_response = requests.get(f"https://production.brntgs.expert.de/api/search/article?webcode={webcode}", headers=headers)
    title_data = title_response.json()
    product_title = title_data.get("seoPageTitle").split(" - bei expert kaufen")[0] if title_data.get("seoPageTitle") else title_data.get("article", {})
    html_file = create_html_report(all_offers, product_title, webcode, discount)
    webbrowser.open(f'file://{html_file}')

# Programm endet automatisch
print("\nScript beendet.")