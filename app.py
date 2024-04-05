from flask import Flask, render_template, request, redirect, url_for, session
from folium.plugins import HeatMap
import pandas as pd
import folium
import os
from werkzeug.utils import secure_filename
import platform
import io
from base64 import b64encode
import sqlite3

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv'}

app = Flask(__name__)

app.config['SECRET_KEY'] = 'sua_chave_secreta_aqui'

app.config['UPLOAD_FOLDER'] = 'uploads'

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Verifique as credenciais do usuário (pode ser uma comparação simples por enquanto)
        if username == 'admin' and password == 'admin':
            # Defina uma sessão para indicar que o usuário está logado
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', mensagem_erro='Credenciais inválidas. Tente novamente.')

    return render_template('login.html')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

df = pd.DataFrame()
intervalo_minutos = 3


def carregar_dataframe_csv(caminho):
    try:
        print(f'tentando carregar o arquivo CSV {caminho}')
        global df
        df = pd.read_csv(caminho, encoding='ISO-8859-1')
        
        # Verifique se as colunas 'Data' e 'Hora' existem no DataFrame
        if 'Data' not in df.columns or 'Hora' not in df.columns:
            raise ValueError("O arquivo CSV não contém as colunas 'Data' e 'Hora'.")

        # Crie a coluna 'DataHora' a partir das colunas 'Data' e 'Hora'
        # df['DataHora'] = pd.to_datetime(df['Data'] + ' ' + df['Hora'], format='%d/%m/%Y %I:%M:%S %p')
        df['DataHora'] = pd.to_datetime(df['Data'] + ' ' + df['Hora'], format='%d/%m/%Y %H:%M:%S')

        # Converta as colunas 'Latitude' e 'Longitude' para float
        df['Latitude'] = df['Latitude'].str.replace(',', '.').astype(float)
        df['Longitude'] = df['Longitude'].str.replace(',', '.').astype(float)

        # Verifique se a coluna 'DataHora' foi criada com sucesso
        if 'DataHora' not in df.columns:
            raise ValueError("A coluna 'DataHora' não foi criada com sucesso.")
        
        print("DataFrame carregado com sucesso")
        print(df.head())

        return df
    except Exception as e:
        print(f'Erro ao carregar arquivo CSV: {e}')
        return pd.DataFrame()
def criar_mapa(df_filtrado, intervalo_minutos=3):
    if 'DataHora' not in df_filtrado.columns:
        print("A coluna 'DataHora' não está presente no DataFrame")
        return None

    # Criando camadas para cada dia
    layers = {}
    for data in pd.date_range(start=df_filtrado['DataHora'].min().date(), end=df_filtrado['DataHora'].max().date(), freq='D'):
        layers[data.strftime('%d/%m/%Y')] = folium.FeatureGroup(name=data.strftime('%d/%m/%Y'))

    mapa = folium.Map(location=[df_filtrado.iloc[0]['Latitude'], df_filtrado.iloc[0]['Longitude']], zoom_start=14)

    # Adicionando camadas ao mapa
    for layer_name, layer in layers.items():
        layer.add_to(mapa)

    # Adicionando camada para o estilo de satélite do Google Maps
    folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google Maps Hybrid', name='Google Maps (Hybrid)').add_to(mapa)

    # Criando camada para HeatMap
    df_velocidade_zero = df_filtrado[df_filtrado['Velocidade'] == 0]
    dados_heatmap = df_velocidade_zero[['Latitude', 'Longitude']].values.tolist()
    HeatMap(dados_heatmap).add_to(mapa)

    tempo_anterior = None

    # Iterando sobre os dados com intervalo_minutos
    for _, row in df_filtrado.iterrows():
        if tempo_anterior is None or (row['DataHora'] - tempo_anterior).seconds >= intervalo_minutos * 60:
            latitude, longitude = row['Latitude'], row['Longitude']
            google_maps_link = f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"
            popup_content = f"{row['Placa']} - {row['Data']} {row['Hora']} - Velocidade: {row['Velocidade']} km/h - LatLong: {[latitude, longitude]}<br><a href='{google_maps_link}' target='_blank'>Ver no Google Maps</a>"

            marker = folium.Marker(location=[latitude, longitude],
                                    popup=folium.Popup(popup_content, max_width=300)
                                    ).add_to(layers[row['DataHora'].date().strftime('%d/%m/%Y')])

            tempo_anterior = row['DataHora']

    # Adicionando controle de camadas ao mapa
    folium.LayerControl().add_to(mapa)

    caminho_mapa = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static', 'mapa_deslocamento.html')
    mapa.save(caminho_mapa)

    return caminho_mapa


# def criar_mapa(df_filtrado, intervalo_minutos=3):
#     if 'DataHora' not in df_filtrado.columns:
#         print("A coluna 'DataHora' não está presente no DataFrame")
#         return None

#     mapa = folium.Map(location=[df_filtrado.iloc[0]['Latitude'], df_filtrado.iloc[0]['Longitude']], zoom_start=14)
#     # folium.TileLayer("cartodbpositron").add_to(mapa)
#     folium.TileLayer('https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', attr='Google Maps Satellite', name='Google Maps (Satellite)').add_to(mapa)
#     # Criando camada para HeatMap
#     df_velocidade_zero = df_filtrado[df_filtrado['Velocidade'] == 0]
#     dados_heatmap = df_velocidade_zero[['Latitude', 'Longitude']].values.tolist()
#     HeatMap(dados_heatmap).add_to(mapa)

#     # Definindo intervalo de dias
#     data_inicio = df_filtrado['DataHora'].min().date()
#     data_fim = df_filtrado['DataHora'].max().date()

#     # Criando camadas para cada dia
#     for data in pd.date_range(start=data_inicio, end=data_fim, freq='D'):
#         df_dia = df_filtrado[df_filtrado['DataHora'].dt.date == data.date()]
#         layer = folium.FeatureGroup(name=data.strftime('%d/%m/%Y'))

#         for _, row in df_dia.iterrows():
#             latitude, longitude = row['Latitude'], row['Longitude']
#             google_maps_link = f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"
#             popup_content = f"{row['Placa']} - {row['Data']} {row['Hora']} - Velocidade: {row['Velocidade']} km/h - LatLong: {[latitude, longitude]}<br><a href='{google_maps_link}' target='_blank'>Ver no Google Maps</a>"

#             marker = folium.Marker(location=[latitude, longitude],
#                                     popup=folium.Popup(popup_content, max_width=300)
#                                     ).add_to(layer)

#         layer.add_to(mapa)

#     # Adicionando controle de camadas ao mapa
#     folium.LayerControl().add_to(mapa)

#     caminho_mapa = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static', 'mapa_deslocamento.html')
#     mapa.save(caminho_mapa)

#     return caminho_mapa
# def criar_mapa(df_filtrado):
    
#     print("Função criar_mapa chamada com DataFrame:")
#     print(df_filtrado)
#     if 'DataHora' not in df_filtrado.columns:
#         print("A coluna 'DataHora' não está presente no DataFrame")
#     mapa = folium.Map(location=[df_filtrado.iloc[0]['Latitude'], df_filtrado.iloc[0]['Longitude']], zoom_start=14)

#     df_velocidade_zero = df_filtrado[df_filtrado['Velocidade'] == 0]
#     dados_heatmap = df_velocidade_zero[['Latitude', 'Longitude']].values.tolist()

#     HeatMap(dados_heatmap).add_to(mapa)
#     tempo_anterior = None

#     for _, row in df_filtrado.iterrows():
#         if tempo_anterior is None or (row['DataHora'] - tempo_anterior).seconds >= intervalo_minutos * 60:
#             latitude, longitude = row['Latitude'], row['Longitude']
#             google_maps_link = f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"
#             popup_content = f"{row['Placa']} - {row['Data']} {row['Hora']} - Velocidade: {row['Velocidade']} km/h - LatLong: {[latitude, longitude]}<br><a href='{google_maps_link}' target='_blank'>Ver no Google Maps</a>"

#             marker = folium.Marker(location=[latitude, longitude],
#                                     popup=folium.Popup(popup_content, max_width=300)
#                                     ).add_to(mapa)

#             tempo_anterior = row['DataHora']
#     # line_points = df_velocidade_zero[['Latitude', 'Longitude']]
#     caminho_mapa = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static', 'mapa_deslocamento.html')
    
#     lines_group = folium.FeatureGroup(name="Lines").add_to(mapa)
#     # lines_group.add_child(folium.PolyLine(locations=line_points, weight=3,color = 'yellow'))
#     # folium.LayerControl().add_to(mapa)
#     # folium.TileLayer("cartodbpositron").add_to(mapa)
    
#     mapa.save(caminho_mapa)
    
#     return caminho_mapa
from flask import send_from_directory


@app.route('/mapa_gerado/<filename>')
def mapa_gerado(filename):
    # Retorne o arquivo HTML gerado para download
    return send_from_directory('static', filename)


@app.route('/mapa_deslocamento')
def mapa_deslocamento():
    return render_template('mapa_deslocamento.html')

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))

    global df

    mapa_gerado = False
    caminho_mapa = None
    
    if request.method == 'POST':
        print("Método POST detectado")
        print("Dados do formulário:")
        print(request.form)
        print("Arquivos enviados:")
        print(request.files)
        data_inicial = request.form['data_inicial']
        hora_inicial = request.form['hora_inicial']
        data_final = request.form['data_final']
        hora_final = request.form['hora_final']

        if not all([data_inicial, hora_inicial, data_final, hora_final]):
            return render_template('index.html', mapa_gerado=False, mensagem_erro="Forneça todas datas e horas")
        if 'arquivo_csv' not in request.files:
            return render_template('index.html', mapa_gerado=False, mensagem_erro="Nenhum arquivo enviado")
        
        file = request.files['arquivo_csv']

        if file.filename == '':
            return render_template('index.html', mapa_gerado=False, mensagem_erro="Nenhum arquivo enviado")
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename)))
            os.makedirs('static', exist_ok=True)

            # Certifique-se de que o diretório 'uploads' exista
            
            df = carregar_dataframe_csv(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            filtro = ((df['DataHora'] >= pd.to_datetime(f'{data_inicial} {hora_inicial}', format='%Y-%m-%d %H:%M:%S')) &
                    (df['DataHora'] <= pd.to_datetime(f'{data_final} {hora_final}', format='%Y-%m-%d %H:%M:%S')))
            df_filtrado = df[filtro].copy()
            print(df_filtrado)
            
            if df_filtrado.empty:
                return render_template('index.html', mapa_gerado=False, mensagem_erro=f"Não há dados no intervalo de datas especificado: {data_inicial} {hora_inicial} - {data_final} {hora_final}")
            
            caminho_mapa = criar_mapa(df_filtrado)
            mapa_gerado = True
    if mapa_gerado:
        link_download = f"/mapa_gerado/{os.path.basename(caminho_mapa)}"
    else:
        link_download = None

    return render_template('index.html', mapa_gerado=mapa_gerado, caminho_mapa=caminho_mapa, link_download=link_download)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

def abrir_mapa_no_navegador():
    # Determine o sistema operacional:
    sistema_operacional = platform.system()

    # caminho do arquyivo html gerado:
    caminho_arquivo_html = os.path.join('static', 'mapa_deslocamento.html')

    # abra o arquivo no navegador padrão combase no sistema operacional
    if sistema_operacional == 'Windows':
        os.startfile(caminho_arquivo_html)
    elif sistema_operacional =='Linux':
        os.system('xdg-open' + caminho_arquivo_html)
    else:
        print('Sistema operacional não suportado')

# abrir_mapa_no_navegador()
        



if __name__ == '__main__':
    app.run(debug=True)