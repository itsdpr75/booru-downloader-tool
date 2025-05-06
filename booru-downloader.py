import requests
from bs4 import BeautifulSoup
import os
import time
from tqdm import tqdm

def get_total_pages(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    # Aquí debes identificar cómo se muestra la paginación en el sitio
    # Este es un ejemplo genérico, ajústalo según la estructura del sitio
    pagination = soup.find('div', class_='pagination')
    if pagination:
        last_page = pagination.find_all('a')[-1].text
        return int(last_page)
    return 1

def get_file_urls(page_url):
    response = requests.get(page_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    # Ajusta este selector según la estructura del sitio
    file_links = soup.find_all('a', class_='file-link')
    return [link['href'] for link in file_links]

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
    search_url = input("Introduce el enlace de la página con la búsqueda realizada: ")
    total_pages = get_total_pages(search_url)
    
    all_file_urls = []
    for page in range(1, total_pages + 1):
        page_url = f"{search_url}&page={page}"  # Ajusta esto según la estructura de URL del sitio
        all_file_urls.extend(get_file_urls(page_url))
    
    total_files = len(all_file_urls)
    print(f"Se han encontrado {total_files} archivos para descargar.")
    
    proceed = input("¿Deseas proceder con la descarga? (s/n): ").lower()
    if proceed != 's':
        print("Descarga cancelada.")
        return
    
    download_folder = "descarga"
    os.makedirs(download_folder, exist_ok=True)
    
    for i, file_url in enumerate(all_file_urls, 1):
        print(f"\nDescargando archivo {i} de {total_files}")
        try:
            filepath = download_file(file_url, download_folder)
            print(f"Archivo guardado en: {filepath}")
        except Exception as e:
            print(f"Error al descargar {file_url}: {e}")
    
    print("\nDescarga completada.")

if __name__ == "__main__":
    main()
