import streamlit as st
from streamlit_option_menu import option_menu
from datetime import date
import pandas as pd
import numpy as np
import os
import requests
from geopy.geocoders import Nominatim
import textwrap
from streamlit_lottie import st_lottie
import io
import xlsxwriter
import folium
from streamlit_folium import st_folium


NUMBER_INPUT    =  "number_input"
SELECTBOX       =  "selectbox"
DATE_INPUT      =  "date_input"
CHECKBOX        =  "checkbox"
TEXTBOX         =  "text_input"

CENTRO_PENINSULA= [40.3952443,	-3.703458799999999]



tipo_busqueda_filter = {
    "Skatepark": "skatepark",
    "Skateshop": "skateshop"
}

#tipo_busquete_filter = {
#    "Skatepark": "skatepark"
#}

tipo_formato_filter = {
    "CSV": "csv",
    "Excel": "excel"
}




st.set_page_config(page_title="Skatepar/Skateshop finder", layout="wide")
# Título del proyecto
st.title("Wandanataleon Skatepark finder - MVP V1")

# Configuración Produccion
google_places_api_key = st.secrets["GP_AK"]

#@st.cache_data
def convert_for_download(df):
    return df.to_csv().encode("utf-8")


def renderiza_mapa(df, centro=CENTRO_PENINSULA, zoom=9):


    print ("Renderizando el fucking mapa...")
    
    # Inicializar el estado si no existe
    if "markers" not in st.session_state:
        st.session_state["markers"] = []
    if "center" not in st.session_state:
        st.session_state["center"] = centro
    if "zoom" not in st.session_state:
        st.session_state["zoom"] = zoom

    st.session_state["skateparks"] = df
    print (f"dataframe: [{st.session_state['skateparks']}]")

    if "skateparks" in st.session_state:
        m = folium.Map(location=st.session_state["center"], zoom_start=st.session_state["zoom"])
        fg = folium.FeatureGroup(name="Markers")
    
    # Crear el mapa centrado
    m = folium.Map(location=st.session_state["center"], zoom_start=st.session_state["zoom"])

    # Crear un grupo de características para los marcadores
    fg = folium.FeatureGroup(name="Markers")

    # Añadir los marcadores de prueba
    for park in st.session_state["skateparks"].itertuples():
        #print  (f"lat[{park.LATITUD}] lon [{park.LONGITUD}]")ç
        popup_html = f"""
            <strong>{park.NOMBRE}</strong><br>
            Dirección: {park.DIRECCIÓN}<br>
            <a href="{park.GOOGLE_MAPS_URL}" target="_blank">Ver en Google Maps</a>
        """

        marker = folium.Marker(
            location=[float(park.LATITUD), float(park.LONGITUD)],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=park.NOMBRE,
            icon=folium.Icon(color="blue", icon="skateboard", prefix="fa")
        )
        fg.add_child(marker)
        st.session_state["markers"].append(marker)

    # Añadir los marcadores almacenados en session_state
    for marker in st.session_state["markers"]:
        fg.add_child(marker)


    # Renderizar el mapa
    output = st_folium(
        m,
        center=st.session_state["center"],
        zoom=st.session_state["zoom"],
        key="new",
        feature_group_to_add=fg,
        height=500,
        width=900,
    )
    
    st.write("Número de marcadores:", len(st.session_state["markers"]))




def obtener_coordenadas_nominatim(codigo_postal, pais=''):
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={codigo_postal},{pais}&format=json&limit=1"
        headers = {"User-Agent": "skatepark_finder_v1 (sandro.lescano@gmail.com)"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Esto lanza un error si la respuesta no es 200
        data = response.json()
        if data:
            return float(data[0]['lat']), float(data[0]['lon'])
        else:
            raise ValueError(f"No se encontraron coordenadas para: {codigo_postal}, {pais}")
    except requests.RequestException as e:
        raise ValueError(f"Error de red para '{codigo_postal}, {pais}': {str(e)}")    

def obtener_coordenadas_google(ciudad, codigo_postal, pais=''):
    try:
        address = f"{codigo_postal if codigo_postal!=0 else ciudad}, {pais}"
        url = f"https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": address,
            "key": google_places_api_key
        }
        headers = {"User-Agent": "skatepark_finder_v1 (contacto@tucorreo.com)"}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('results'):
            location = data['results'][0]['geometry']['location']
            return float(location['lat']), float(location['lng'])
        else:
            raise ValueError(f"No se encontraron coordenadas para: {address}")
    except requests.RequestException as e:
        raise ValueError(f"Error de red para '{address}': {str(e)}")


def get_google_maps_geoloc(lat, lon):
    return f'https://www.google.com/maps?q={lat},{lon}'

def get_google_maps_url(place_id):
    return f"https://www.google.com/maps/place/?q=place_id:{place_id}"

def obtener_imagenes_google_places(place_id, num_imagenes):
    url = f'https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=photos&key={google_places_api_key}'
    respuesta = requests.get(url)
    fotos = respuesta.json().get('result', {}).get('photos', [])
    imagenes = []
    for foto in fotos[:int(num_imagenes)]:
        photo_reference = foto.get('photo_reference')
        imagen_url = f'https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={photo_reference}&key={google_places_api_key}'
        imagenes.append(imagen_url)
    return imagenes

def obtener_direccion_completa(place_id):
    url = f'https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=address_components&key={google_places_api_key}'
    respuesta = requests.get(url)
    detalles = respuesta.json().get('result', {}).get('address_components', [])
    direccion_completa = " ".join([comp['long_name'] for comp in detalles if 'long_name' in comp])
    return direccion_completa

def buscar_skateparks(tipo_busqueda, codigo_postal, pais, ciudad, lat, lon, radio_km, imagenes_por_lugar):
    
    print(f"Radio de busqueda  [{radio_km if int(radio_km)>0 else 'Máximo'}] Kilometros alrededor de {codigo_postal or ciudad}")

    if int(radio_km) > 0:
        print("Busqueda por radio (KM)")
        url = f'https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lon}&radius={int(radio_km) * 1000}&type=park&keyword={tipo_busqueda}&key={google_places_api_key}'
    else:
        print("Busqueda por texto")
        query = f"{tipo_busqueda} en {codigo_postal} {ciudad} {pais}"
        url = f'https://maps.googleapis.com/maps/api/place/textsearch/json?query={query}&key={google_places_api_key}'
    
    respuesta = requests.get(url)
    lugares = respuesta.json().get('results', [])
    skateparks = []

    for lugar in lugares:
        nombre = lugar.get('name')
        #direccion = lugar.get('vicinity')
        place_id = lugar.get('place_id')
        direccion = obtener_direccion_completa(place_id)
        gps = lugar.get('geometry', {}).get('location', {})
        lat_gps = gps.get('lat')
        lon_gps = gps.get('lng')
        imagenes = obtener_imagenes_google_places(place_id, imagenes_por_lugar)



        skateparks.append({
            'NOMBRE': str(nombre).replace('"', ''),
            'DIRECCIÓN': direccion,
            'LATITUD': lat_gps,
            'LONGITUD': lon_gps,
            'GOOGLE_MAPS_URL': get_google_maps_url(place_id),
            'GOOGLE_MAPS_GEO_PIN': get_google_maps_geoloc(lat_gps, lon_gps)
        })

    return skateparks



def guardar_resultados(skateparks, archivo='skateparks', formato='csv'):
    df = pd.DataFrame(skateparks)
    if formato == 'excel':
        if not archivo.endswith('.xlsx'):
            archivo += '.xlsx'
        df.to_excel(archivo, index=False)
        print(f"Resultados guardados en Excel: {archivo}")
    else:
        if not archivo.endswith('.csv'):
            archivo += '.csv'
        df.to_csv(archivo, index=False)
        print(f"Resultados guardados en CSV: {archivo}")

def dame_skateparks(codigo_postal,pais,ciudad,radio,imagenes,tipo_busqueda):
    df_skateparks = None
    lat = None
    lon = None
    
    try:   
        
        print (f"Empezando la busqueda de {tipo_busqueda}s: ")
        print ("----------------------------")
        print ('codigo_postal     [{}  ]: '.format(codigo_postal))
        print ('pais              [{}  ]: '.format(pais))
        print ('ciudad            [{}  ]: '.format(ciudad))
        print ('numero_imagenes   [{}  ]: '.format(imagenes))
        print ('radio_busqueda    [{}KM]: '.format(radio))
        print ('nombre_fichero    [{}  ]: '.format(tipo_busqueda))


        #lat, lon = obtener_coordenadas(codigo_postal, pais)
        lat, lon =obtener_coordenadas_google(ciudad, codigo_postal, pais)
        print(f"lat[{lat}] - lon [{lon}] |lat type[{type(lat)}] lon type[{type(lon)}]")
        print(f"Buscando skateparks alrededor de {codigo_postal if codigo_postal !=0 else ciudad} ({lat}, {lon})...")
        
        skateparks = buscar_skateparks(tipo_busqueda, codigo_postal, pais, ciudad, lat, lon, radio, int(imagenes))
        #print (f"Skateparks: [{skateparks}]")
        #print (f"skateparks[{skateparks}]")
        if skateparks:
            # Convertir a DataFrame para st.map()
            df_skateparks = pd.DataFrame(skateparks)
            st.session_state["df_skateparks"] = df_skateparks
            st.session_state["lat"] = lat
            st.session_state["lon"] = lon
            
    except Exception as e:
        st.error(f"Error {str(e)}") 
    
    return df_skateparks, lat, lon 


def renderiza_dataframe():
                # Configurar la columna como enlaces
    st.data_editor(
        st.session_state["skateparks"],
        column_config={
            "GOOGLE_MAPS_URL": st.column_config.LinkColumn(
                "GOOGLE_MAPS_URL",
                help="Haz clic para visitar el sitio del skatepark",
                width="large"  # Ajusta el ancho de la columna
            ),
            "GOOGLE_MAPS_GEO_PIN": st.column_config.LinkColumn(
                "GOOGLE_MAPS_GEO_PIN",
                help="Haz clic para visitar el sitio del skatepark",
                width="large"  # Ajusta el ancho de la columna
            )
        },
        hide_index=True
    )

def descarga_fichero(df, formato, nombre_fichero, codigo_postal, ciudad, pais, radio):
    
    ext = 'xlsx' if formato == 'excel' else 'csv'
    archivo = f"{nombre_fichero}_{codigo_postal if int(codigo_postal) !=0 else ciudad}_{pais}{f'_{radio}KM' if int(radio) !=0 and int(radio) != '' else ''}.{ext}"

    if formato == 'excel':
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Skateparks")
            writer.close()
        output.seek(0)
        st.download_button(
            label="📥 Descargar Excel",
            data=output,
            file_name=archivo,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Descargar CSV",
            data=csv,
            file_name=archivo,
            mime="text/csv"
        )


def custom_input(label, session_key, input_type, options=None, default=None, **kwargs):
    """Crea un input de Streamlit con manejo de session_state y valores internos."""
    
    # Solo inicializa el estado si no está definido
    if session_key not in st.session_state:
        if input_type == "selectbox" and options:
            st.session_state[session_key] = default or list(options.keys())[0]
        elif input_type == "number_input":
            st.session_state[session_key] = default or 0
        elif input_type == "checkbox":
            st.session_state[session_key] = default or False
        elif input_type == "date_input":
            st.session_state[session_key] = default or date.today()
        elif input_type == "text_input":
            st.session_state[session_key] = default or ""
        else:
            raise ValueError(f"Unsupported input type: {input_type}")
  
    # Crear el input correspondiente
    current_value = st.session_state[session_key]
    if input_type == "selectbox" and options:
        selected_label = st.selectbox(label, list(options.keys()), index=list(options.keys()).index(current_value), **kwargs)
        if selected_label != current_value:
            st.session_state[session_key] = selected_label
        
        return options[selected_label]
    
    elif input_type == "number_input":
        value = st.number_input(label, value=current_value, **kwargs)
        if value != current_value:
            st.session_state[session_key] = value
        return value
    
    elif input_type == "checkbox":
        value = st.checkbox(label, value=current_value, **kwargs)
        if value != current_value:
            st.session_state[session_key] = value
        return value
    
    elif input_type == "date_input":
        value = st.date_input(label, value=current_value, **kwargs)
        if value != current_value:
            st.session_state[session_key] = value
        return value
    
    elif input_type == "text_input":
        value = st.text_input(label, value=current_value, **kwargs)
        if value != current_value:
            st.session_state[session_key] = value
        return value
    
    else:
        raise ValueError(f"Unsupported input type: {input_type}")


tipo_busqueda_input     = custom_input("Tipo de busqueda",  "tipo_busqueda", SELECTBOX, options=tipo_busqueda_filter)
pais_input              = custom_input("Pais",              "pais",      TEXTBOX  ,help="Introduce el país de busqueda", default="España")
ciudad_input            = custom_input("Ciudad",            "ciudad",    TEXTBOX, help="Introduce la ciudad de busqueda", default="Madrid")
cp_input                = custom_input("Código postal",     "cp",        NUMBER_INPUT, help="Introduce el codigo postal", disabled= ciudad_input != '' )
radiokm_input           = custom_input("Radio",             "radiokm",   NUMBER_INPUT, help="Introduce el radio  de busqueda en KM", disabled= ciudad_input != ''  )
tipo_formato_input      = custom_input("Tipo de formato",  "tipo_formato", SELECTBOX, options=tipo_formato_filter)



if st.button(f"Buscar {tipo_busqueda_input}s"):

    # 🧼 Limpiar variables de sesión después de mostrar y permitir descarga
    st.session_state.pop("skateparks", None)
    st.session_state.pop("markers", None)
    st.session_state.pop("center", None)
    st.session_state.pop("zoom", None)
    skateparks_df, lat, lon = dame_skateparks(cp_input, pais_input, ciudad_input, radiokm_input, 0, tipo_busqueda_input)
    
    
    # Inicializar el estado si no existe
    if "markers" not in st.session_state:
        st.session_state["markers"] = []
    if "center" not in st.session_state:
        st.session_state["center"] = [float(lat), float(lon)]
    if "zoom" not in st.session_state:
        st.session_state["zoom"] = 9

    st.session_state["center"] = [float(lat), float(lon)]
    st.session_state["zoom"] = 9
    st.session_state["skateparks"] = skateparks_df

if "skateparks" in st.session_state:
    renderiza_dataframe()
    m = folium.Map(location=st.session_state["center"], zoom_start=st.session_state["zoom"])
    fg = folium.FeatureGroup(name="Markers")

    # Crear el mapa centrado
    m = folium.Map(location=st.session_state["center"], zoom_start=st.session_state["zoom"])

    # Crear un grupo de características para los marcadores
    fg = folium.FeatureGroup(name="Markers")

    # Añadir los marcadores de prueba
    #for park in skateparks:
    for park in st.session_state["skateparks"].itertuples():
        popup_html = f"""
            <strong>{park.NOMBRE}</strong><br>
            Dirección: {park.DIRECCIÓN}<br>
            <a href="{park.GOOGLE_MAPS_URL}" target="_blank">Ver en Google Maps</a>
        """
        marker = folium.Marker(
            location=[float(park.LATITUD), float(park.LONGITUD)],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=park.NOMBRE,
            icon=folium.Icon(color="blue", icon="skateboard", prefix="fa")
        )
        fg.add_child(marker)
        st.session_state["markers"].append(marker)

    # Añadir los marcadores almacenados en session_state
    for marker in st.session_state["markers"]:
        fg.add_child(marker)

    # Renderizar el mapa
    output = st_folium(
        m,
        center=st.session_state["center"],
        zoom=st.session_state["zoom"],
        key="new",
        feature_group_to_add=fg,
        height=600,
        width='100%',
    )

    st.write("Número de marcadores:", len(st.session_state["markers"]))
    #renderiza_mapa(skateparks_df, CENTRO_PENINSULA, 9)

    ext = 'xlsx' if tipo_formato_input == 'excel' else 'csv'
    archivo = f"{tipo_busqueda_input}_{cp_input if int(cp_input) !=0 else ciudad_input}_{pais_input}{f'_{radiokm_input}KM' if int(radiokm_input) !=0 and int(radiokm_input) != '' else ''}.{ext}"

    if tipo_formato_input == 'excel':
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            st.session_state["skateparks"].to_excel(writer, index=False, sheet_name="Skateparks")
            writer.close()
        output.seek(0)
        st.download_button(
            label="📥 Descargar Excel",
            data=output,
            file_name=archivo,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        csv = st.session_state["skateparks"].to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Descargar CSV",
            data=csv,
            file_name=archivo,
            mime="text/csv"
                    )
else:
    st.warning("Sin resultados: No se encontraron skateparks")


