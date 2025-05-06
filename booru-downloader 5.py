import requests
from bs4 import BeautifulSoup
import os
from tqdm import tqdm
import re

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

def get_total_pages(url):
    response = requests.get(url.replace('{{page}}', '1'))
    soup = BeautifulSoup(response.text, 'html.parser')
    pagination_links = soup.find_all('a', href=re.compile(r'\?page=\d+'))
    if pagination_links:
        page_numbers = [int(re.search(r'\d+', link['href']).group()) for link in pagination_links]
        return max(page_numbers)
    return 1

def get_file_urls(page_url, file_link_selector, file_url_attribute):
    response = requests.get(page_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    file_links = soup.select(file_link_selector)
    return [link[file_url_attribute] for link in file_links]

def get_download_url(file_page_url, download_link_selector, base_url):
    response = requests.get(file_page_url)
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

def download_file(url, folder):
    local_filename = url.split('/')[-1]
    filepath = os.path.join(folder, local_filename)
    
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        total_size = int(r.headers.get('content-length', 0))
        
        with open(filepath, 'wb') as f, tqdm(
            desc=local_filename,
            total=total_size,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
        ) as progress_bar:
            for chunk in r.iter_content(chunk_size=8192):
                size = f.write(chunk)
                progress_bar.update(size)
    
    return filepath

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
                print(f"Archivo guardado en: {filepath}")
            else:
                print(f"No se pudo encontrar el enlace de descarga para {file_url}")
        except Exception as e:
            print(f"Error al procesar {file_url}: {e}")
    
    print("\nDescarga completada.")

if __name__ == "__main__":
    main()
