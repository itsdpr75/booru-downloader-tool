import requests
from bs4 import BeautifulSoup
import os
from tqdm import tqdm
import re
import time
import signal
import sys
import math
from concurrent.futures import ThreadPoolExecutor

# Configuración global
MAX_RETRIES = 3
RETRY_DELAY = 5

def signal_handler(sig, frame):
    print("\nInterrupción detectada. Finalizando el programa...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def get_user_input():
    print("Por favor, proporciona la siguiente información sobre la estructura del sitio web:")
    base_url = input("URL base del sitio (ej. https://example.com): ")
    search_url = input("URL completa de la búsqueda con marcador de página (usa '{{page}}' para indicar el lugar del número de página): ")
    file_link_selector = input("Selector CSS para los enlaces de archivos (ej. 'a.post-preview-link'): ")
    file_url_attribute = input("Atributo del enlace que contiene la URL del archivo (ej. 'href'): ")
    download_link_selector = input("Selector CSS para el contenedor del enlace de descarga (ej. 'li#post-info-size'): ")
    
    return {
        'base_url': base_url,
        'search_url': search_url,
        'file_link_selector': file_link_selector,
        'file_url_attribute': file_url_attribute,
        'download_link_selector': download_link_selector
    }

def make_request(url, retries=MAX_RETRIES):
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            if attempt < retries - 1:
                print(f"Error al acceder a {url}: {e}. Reintentando en {RETRY_DELAY} segundos...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"Error al acceder a {url} después de {retries} intentos: {e}")
                return None
    return None

def get_total_pages(url):
    response = make_request(url.replace('{{page}}', '1'))
    if not response:
        return 1
    soup = BeautifulSoup(response.text, 'html.parser')
    pagination_links = soup.find_all('a', href=re.compile(r'\?page=\d+'))
    if pagination_links:
        page_numbers = [int(re.search(r'\d+', link['href']).group()) for link in pagination_links]
        return max(page_numbers)
    return 1

def get_file_urls(page_url, file_link_selector, file_url_attribute):
    response = make_request(page_url)
    if not response:
        return []
    soup = BeautifulSoup(response.text, 'html.parser')
    file_links = soup.select(file_link_selector)
    return [link[file_url_attribute] for link in file_links if file_url_attribute in link.attrs]

def get_download_url(file_page_url, download_link_selector, base_url):
    response = make_request(file_page_url)
    if not response:
        return None
    soup = BeautifulSoup(response.text, 'html.parser')
    download_container = soup.select_one(download_link_selector)
    if download_container:
        download_link = download_container.find('a', href=True)
        if download_link:
            download_url = download_link['href']
            if download_url.startswith('/'):
                download_url = base_url + download_url
            return download_url
    return None

def get_file_size(url):
    response = make_request(url, retries=1)
    if response and 'content-length' in response.headers:
        return int(response.headers['content-length'])
    return 0

def format_size(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

def calculate_total_size(file_urls, config):
    total_size = 0
    print("Calculando el tamaño total de la descarga...")

    def process_file(file_url):
        if not file_url.startswith(('http://', 'https://')):
            file_url = config['base_url'] + file_url
        download_url = get_download_url(file_url, config['download_link_selector'], config['base_url'])
        if download_url:
            return get_file_size(download_url)
        return 0

    with ThreadPoolExecutor(max_workers=10) as executor:
        file_sizes = list(tqdm(executor.map(process_file, file_urls), total=len(file_urls), desc="Procesando archivos"))

    total_size = sum(file_sizes)
    print("\nCálculo completado.")
    return total_size

def download_file(url, folder, retries=MAX_RETRIES):
    local_filename = url.split('/')[-1]
    filepath = os.path.join(folder, local_filename)
    
    for attempt in range(retries):
        try:
            with requests.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                
                with open(filepath, 'wb') as f, tqdm(
                    desc=local_filename,
                    total=total_size,
                    unit='iB',
                    unit_scale=True,
                    unit_divisor=1024,
                    dynamic_ncols=True
                ) as progress_bar:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            size = f.write(chunk)
                            progress_bar.update(size)
            
            if os.path.getsize(filepath) != total_size:
                raise Exception("El tamaño del archivo descargado no coincide con el tamaño esperado.")
            
            return filepath
        except Exception as e:
            if attempt < retries - 1:
                print(f"Error al descargar {url}: {e}. Reintentando en {RETRY_DELAY} segundos...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"Error al descargar {url} después de {retries} intentos: {e}")
                if os.path.exists(filepath):
                    os.remove(filepath)
                return None
    return None

def main():
    config = get_user_input()
    total_pages = get_total_pages(config['search_url'])
    
    all_file_urls = []
    for page in range(1, total_pages + 1):
        page_url = config['search_url'].replace('{{page}}', str(page))
        print(f"Accediendo a la página: {page_url}")
        all_file_urls.extend(get_file_urls(page_url, config['file_link_selector'], config['file_url_attribute']))
    
    total_files = len(all_file_urls)
    print(f"Se han encontrado {total_files} archivos para descargar.")
    
    total_size = calculate_total_size(all_file_urls, config)
    print(f"Tamaño total de la descarga: {format_size(total_size)}")
    
    proceed = input("¿Deseas proceder con la descarga? (s/n): ").lower()
    if proceed != 's':
        print("Descarga cancelada.")
        return
    
    download_folder = "descarga"
    os.makedirs(download_folder, exist_ok=True)
    
    for i, file_url in enumerate(all_file_urls, 1):
        print(f"\nProcesando archivo {i} de {total_files}")
        try:
            if not file_url.startswith(('http://', 'https://')):
                file_url = config['base_url'] + file_url
            download_url = get_download_url(file_url, config['download_link_selector'], config['base_url'])
            if download_url:
                filepath = download_file(download_url, download_folder)
                if filepath:
                    print(f"Archivo guardado en: {filepath}")
                else:
                    print(f"No se pudo descargar el archivo desde {download_url}")
            else:
                print(f"No se pudo encontrar el enlace de descarga para {file_url}")
        except Exception as e:
            print(f"Error al procesar {file_url}: {e}")
    
    print("\nDescarga completada.")

if __name__ == "__main__":
    main()
