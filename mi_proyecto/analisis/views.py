from django.shortcuts import render
from django.http import HttpResponse
from datetime import datetime
from django.shortcuts import render, redirect
from django.core import serializers
from django.contrib.auth.decorators import login_required
from .models import Carpeta, Archivo, Analisis, Aplicacion, Resultado, Preferencias, Grafico, Grafico_Imagen, Tabla
from .forms import AnalisisForm, PreferenciasForm, CarpetaForm, FileForm, ResultadoViewForm, AnalisisViewForm, ResultadoClasificadorViewForm, ResultadoEntidadesViewForm, WordcloudForm
from xhtml2pdf import pisa
from django.db.models import Q
from .tasks import comenzar_celery
from celery.result import AsyncResult
import json
from django.http import JsonResponse
import zipfile
from nlp_component.nlp import nuevo_wordcloud
import io


@login_required
def home(request): 
    response = redirect('/principal')
    return response

@login_required
def principal(request):
    return render(request, "analisis/principal.html") 

@login_required
def config(request):
    user = request.user

    try:
        preferencias = Preferencias.objects.get(usuario = user)
    except Preferencias.DoesNotExist:
        preferencias = Preferencias(usuario = user, color = 'CLASICO')
    form_preferencias = PreferenciasForm(request.POST or None, request.FILES or None, instance=preferencias)
     
    context = {
        "usuario": user,
        "color_actual" : preferencias.color,
        "form_preferencias" : form_preferencias,
    }

    if form_preferencias.is_valid():
        form_preferencias.save()
        response = redirect('/config')
        return response

    return render(request, "analisis/config.html", context=context) 

@login_required
def carpetas(request):
    usuario_actual = request.user
    context = {
        "carpetas": Carpeta.objects.filter(usuario = usuario_actual).order_by("-id"),
    }
    return render(request, "analisis/carpetas.html", context= context) 

@login_required
def carpeta(request, id_carpeta):

    usuario_actual = request.user
    carpeta = Carpeta.objects.get(id = id_carpeta)

    if carpeta.usuario != usuario_actual:
        return HttpResponse("No tiene permiso para ver esta carpeta")

    form_file = FileForm(request.POST or None, request.FILES or None, carpeta_id =id_carpeta)
    context = {
        "carpeta": carpeta,
        "archivos": Archivo.objects.filter(carpeta = carpeta),
        "form_file" : form_file,
    }
    if form_file.is_valid():
        for f in request.FILES.getlist('file'):
            nombre = f.name
            archivo = Archivo(nombre =nombre, arch = f, carpeta = carpeta, fecha_creacion = datetime.now())
            archivo.save()
        response = redirect('/carpeta/'+str(carpeta.id))
        return response
    return render(request, "analisis/carpeta.html", context=context) 

@login_required
def aplicacion(request, id_app):

    analisis = Analisis(informe ='')
    aplicacion = Aplicacion.objects.get(id = id_app)
    form_analisis = AnalisisForm(request.POST or None, request.FILES or None, instance=analisis, aplicacion = aplicacion)

    context = {
        "analisis" : analisis,
        "aplicacion": aplicacion,
        "form_analisis" : form_analisis,
    }

    if form_analisis.is_valid():
        form_analisis.save()

        response = redirect('/procesar/'+str(analisis.id))
        return response
    return render(request, "analisis/aplicacion.html", context=context) 


@login_required
def procesar(request, id_analisis):

    analisis = Analisis.objects.get(id = id_analisis)
    carpeta = analisis.carpeta
    archivos = Archivo.objects.filter(carpeta = carpeta)
    modelo = analisis.modelo
    aplicacion = modelo.aplicacion

    if 'error' in request.session:
        del request.session['error']
    
    for archivo in archivos:
        nombre, partition, extension = archivo.arch.name.rpartition('.')
        if extension not in ['txt', 'docx', 'pdf', 'doc', 'zip']: #TODO chequear adentro del zip
            analisis.delete()
            request.session['error'] = "No se soporta el tipo de archivo "+extension+" en la carpeta "+carpeta.nombre+"."
            return redirect('/aplicacion/' + str(aplicacion.id))
        if extension == 'zip':
            with zipfile.ZipFile(archivo.arch, 'r') as zip_ref:
                for file in zip_ref.namelist():
                    name, partition, extension = file.rpartition('.')
                    if extension not in ['txt', 'docx', 'pdf', 'doc']:
                        analisis.delete()
                        request.session['error'] = "No se soporta el tipo de archivo "+extension+" en la carpeta "+carpeta.nombre+"."
                        return redirect('/aplicacion/' + str(aplicacion.id))
    
    context = {
        "aplicacion": aplicacion,
        "analisis" : analisis,
        "id_analisis" : id_analisis,
    }
    return render(request, "analisis/procesar.html", context=context)



@login_required
def resultados(request):

    carpetas = Carpeta.objects.filter(usuario = request.user)
    analisis = None

    if request.method == 'POST':
        form = AnalisisViewForm(request.POST,user_id = request.user.id)
        if form.is_valid():
            carpeta = form.cleaned_data['carpeta']
            fecha = form.cleaned_data['fecha']
            modelo = form.cleaned_data['modelo']
            if carpeta == 'all':
                carpetas = Carpeta.objects.filter(usuario = request.user)
            else:
                carpetas = Carpeta.objects.filter(usuario = request.user, id = carpeta)
            if fecha:
                if modelo != 'all':
                    analisis = Analisis.objects.filter(Q(carpeta__in = carpetas), Q( fecha__lte = fecha), Q(modelo = modelo)).order_by("-id")
                else:
                    analisis = Analisis.objects.filter(Q(carpeta__in = carpetas), Q( fecha__lte = fecha)).order_by("-id")
            else: 
                if modelo != 'all':
                    analisis = Analisis.objects.filter(Q(carpeta__in = carpetas), Q(modelo = modelo)).order_by("-id")
                else:
                    analisis = Analisis.objects.filter(carpeta__in = carpetas).order_by("-id")
    else:
        form = AnalisisViewForm(user_id = request.user.id)
        carpetas = Carpeta.objects.filter(usuario = request.user)
        analisis = Analisis.objects.filter(carpeta__in = carpetas).order_by("-id")

    context = {
        'analisis' : analisis,
        'form' : form,
    }
    return render(request, "analisis/resultados.html",context=context) 





@login_required
def resultado(request, id_analisis):
    """
    TODO: testear que pasa si no hay resultados. ver funcionamiento de try y except

    """

    usuario_actual = request.user
    carpetas = Carpeta.objects.filter(usuario = request.user)
    analisis = Analisis.objects.get(id = id_analisis)
    if analisis.carpeta.usuario != usuario_actual:
        return HttpResponse("No tiene permiso para ver este resultado")
    
    resultados_x_archivo = None
    form = None
    form_c = None
    error = None
    if analisis.modelo.nombre == 'entidades':
        if request.method == 'POST':
            form = ResultadoEntidadesViewForm(request.POST, analisis_id = analisis.id)
            if form.is_valid():
                file_choice = form.cleaned_data['file_choice']
                if file_choice == 'all':
                    entidades = form.cleaned_data.get('entidades')
                    resultados_x_archivo = []
                    archivos = Archivo.objects.filter(carpeta = analisis.carpeta)
                    for archivo in archivos:
                        resultados_archivo = Resultado.objects.filter(analisis = analisis, archivo_origen = archivo)
                        
                        if entidades and ('TODAS' not in entidades):
                            resultados_archivo = [
                                resultado for resultado in resultados_archivo 
                                if any(
                                    entidad in (d['label'] for d in json.loads(resultado.detectado)) 
                                    for entidad in entidades
                                )
                            ]
                        
                        resultados_x_archivo.append(resultados_archivo)
                    resultados = Resultado.objects.filter(analisis = analisis)
                else:
                    resultados = Resultado.objects.filter(analisis = analisis, archivo_origen = Archivo.objects.get(id = file_choice))
                    entidades = form.cleaned_data.get('entidades')
                    if entidades and ('TODAS' not in entidades):
                        resultados = [
                            resultado for resultado in resultados 
                            if any(
                                entidad in (d['label'] for d in json.loads(resultado.detectado)) 
                                for entidad in entidades
                            )
                        ]
                    #no hay resultados_x_archivo porque solo se selecciono un archivo
            else:
                resultados = Resultado.objects.filter(analisis = analisis)
        else:
            form = ResultadoEntidadesViewForm(analisis_id = analisis.id)
            resultados_x_archivo = []
            archivos = Archivo.objects.filter(carpeta = analisis.carpeta)
            for archivo in archivos:
                resultados_archivo = Resultado.objects.filter(analisis = analisis, archivo_origen = archivo)
                resultados_x_archivo.append(resultados_archivo)
            resultados = Resultado.objects.filter(analisis = analisis)
        try:
            imagenes = Grafico_Imagen.objects.filter(analisis = analisis, nombre = 'Wordcloud de entidades')
            grafico_distribucion = Grafico.objects.get(analisis = analisis, nombre = 'Distribucion de entidades') 
            grafico_ents_archivo = Grafico.objects.get(analisis = analisis, nombre = 'Entidades por archivo')
            grafico_comp_archivos = Grafico.objects.get(analisis = analisis, nombre = 'Composicion de entidades por archivo')
            grafico_lineas_ents = Grafico.objects.get(analisis = analisis, nombre = 'Relacion entre numero de linea y entidades')
            grafico_torta = Grafico.objects.get(analisis = analisis, nombre = 'Torta distribucion de entidades')
            tabla_distribucion = Tabla.objects.get(analisis = analisis, nombre = 'Distribucion de entidades')
        except:
            imagenes = None
            grafico_distribucion = None
            grafico_ents_archivo = None
            grafico_comp_archivos = None
            grafico_lineas_ents = None
            grafico_torta = None
            tabla_distribucion = None
            error = "No se detectaron entidades en los archivos."

        try: #separado porque este puede fallar por si solo porque no existieron repeticiones.
            tabla_rep= Tabla.objects.get(analisis = analisis, nombre = 'Entidades que se repiten')
        except:
            tabla_rep = None

        context = {
        'analisis' : analisis,
        'aplicacion' : analisis.modelo.aplicacion,
        'resultados' : resultados,
        'wordclouds' : imagenes,
        'tabla_distribucion' : tabla_distribucion,
        'tabla_rep': tabla_rep,
        'grafico_distribucion' : grafico_distribucion,
        'grafico_ents_archivo' :   grafico_ents_archivo,
        'grafico_comp_archivos' : grafico_comp_archivos,
        'grafico_lineas_ents': grafico_lineas_ents,
        'grafico_torta':    grafico_torta,
        'resultados_x_archivo': resultados_x_archivo,
        'form': form,
        'error': error,
        }
        
        return render(request, "analisis/resultado_entidades.html", context= context)
    
    elif analisis.modelo.nombre == 'clasificador':
        if request.method == 'POST':
            form_c = ResultadoClasificadorViewForm(request.POST, analisis_id = analisis.id)
            if form_c.is_valid():
                file_choice = form_c.cleaned_data['file_choice']
                violentos = form_c.cleaned_data['violentos']
                remitente = form_c.cleaned_data['remitente']
                fecha = form_c.cleaned_data['fecha']
                score = form_c.cleaned_data['score']
                not_adjuntos = form_c.cleaned_data['adjuntos']

                if file_choice == 'all':
                    resultados = Resultado.objects.filter(analisis = analisis).order_by('archivo_origen','numero_linea')
                else:
                    resultados = Resultado.objects.filter(analisis = analisis, archivo_origen = Archivo.objects.get(id = file_choice)).order_by('numero_linea')
                if violentos: #tengo que sacar del resultado los que no son violentos
                    resultados = resultados.exclude(detectado = 'No Violento')
                if not_adjuntos:
                    resultados = resultados.exclude(detectado = 'Adjunto')
                if remitente!= 'all':
                    resultados = resultados.filter(remitente = remitente)
                if fecha:
                    resultados = resultados.filter(Q( fecha_envio__lte = fecha))
                if score:
                    resultados = resultados.filter(Q( score__gte = score))
        else:
            form_c = ResultadoClasificadorViewForm(analisis_id = id_analisis)
            resultados = Resultado.objects.filter(analisis = analisis).order_by('archivo_origen','numero_linea')

        try:
            grafico_distribucion = Grafico.objects.get(analisis = analisis, nombre = 'Distribucion de categorias')
            grafico_torta = Grafico.objects.get(analisis = analisis, nombre = 'Torta distribucion de categorias')
            grafico_categoria_archivo = Grafico.objects.get(analisis = analisis, nombre = 'Composicion de categorias por archivo') 
            grafico_lineas_cats = Grafico.objects.get(analisis = analisis, nombre = 'Relacion numero de linea y frases violentas')
        except:
            error = "No se logró detectar automaticamente ninguna frase posiblemente violenta en los archivos."
            grafico_distribucion = None
            grafico_torta = None
            grafico_categoria_archivo = None
            grafico_lineas_cats = None
        try:
            tabla_distribucion = Tabla.objects.get(analisis = analisis, nombre = 'Distribucion de categorias')
        except:
            tabla_distribucion = None
        try:
            word_cats = Grafico_Imagen.objects.get(analisis = analisis, nombre = 'Wordcloud de clasificacion')
        except:
            word_cats = None
        try: 
            word_violento = Grafico_Imagen.objects.get(analisis = analisis, nombre = 'Wordcloud de violentos')
        except:
            word_violento = None

        context = {
        'analisis' : analisis,
        'aplicacion' : analisis.modelo.aplicacion,
        'resultados' : resultados,
        'tabla_distribucion' : tabla_distribucion,
        'grafico_distribucion' : grafico_distribucion,
        'grafico_torta' : grafico_torta,
        'grafico_categoria_archivo': grafico_categoria_archivo,
        'grafico_lineas_cats':grafico_lineas_cats,
        'word_cats' : word_cats,
        'word_violento' : word_violento,
        'form': form_c,
        'error': error,
        }
        return render(request, "analisis/resultado_clasificador.html", context= context)
    else:
        context = {
        'analisis' : Analisis.objects.filter(carpeta__in = carpetas).order_by("-id")
        }
        return render(request, "analisis/resultados.html", context= context) 




@login_required
def nueva_carpeta(request):
    carpeta = Carpeta(usuario = request.user, fecha_creacion=datetime.now(), ultima_modificacion=datetime.now(), nombre = '')
    form_carpeta = CarpetaForm(request.POST or None, request.FILES or None, instance=carpeta)
    context = {
        'form_carpeta' : form_carpeta,
    }
    if form_carpeta.is_valid():
        form_carpeta.save()
        response = redirect('/carpeta/'+str(carpeta.id))
        return response
    return render(request, "analisis/nueva_carpeta.html", context = context) 


@login_required
def borrar_archivo(request, id_archivo):
    archivo = Archivo.objects.get(id = id_archivo)
    carpeta = archivo.carpeta
    usuario_actual = request.user
    if carpeta.usuario != usuario_actual:
        return HttpResponse("No tiene permiso para borrar este archivo")
    archivo.delete()
    response = redirect('/carpeta/'+str(carpeta.id))
    return response


@login_required
def borrar_carpeta(request, id_carpeta):
    
    carpeta = Carpeta.objects.get(id = id_carpeta)
    usuario_actual = request.user
    if carpeta.usuario != usuario_actual:
        return HttpResponse("No tiene permiso para borrar este archivo")
    carpeta.delete()
    response = redirect('/carpetas')
    return response


@login_required
def borrar_analisis(request, id_analisis):
    analisis = Analisis.objects.get(id = id_analisis)
    usuario_actual = request.user
    if analisis.carpeta.usuario != usuario_actual:
        return HttpResponse("No tiene permiso para borrar este resultado")
    analisis.delete()
    response = redirect('/resultados')
    return response

@login_required
def descargar_resultados_entidades(request, id_analisis, id_archivo):
    # https://github.com/JazzCore/python-pdfkit/wiki/Installing-wkhtmltopdf

    analisis = Analisis.objects.get(id = id_analisis)
    usuario_actual = request.user
    if analisis.carpeta.usuario != usuario_actual:
        return HttpResponse("No tiene permiso para descargar este resultado")
    resultados_x_archivo = []
    if id_archivo == 'all':
        archivos = Archivo.objects.filter(carpeta = analisis.carpeta)
        for archivo in archivos:
            resultados_archivo = Resultado.objects.filter(analisis = analisis, archivo_origen = archivo)
            resultados_x_archivo.append(resultados_archivo)
    else:
        archivo = Archivo.objects.get(id = id_archivo)
        resultados = Resultado.objects.filter(analisis = analisis, archivo_origen = archivo)
        resultados_x_archivo.append(resultados)
    
    html = ''
    for reultados_archivo in resultados_x_archivo:
        for resultado in reultados_archivo:
            html += "<div class='col'> <div>"+ resultado.html+"</div> </div>"
        #agregar pagina al pdf.
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename= "resultados_entidades.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
            return HttpResponse('We had some errors')
    return response


def comenzar_tarea_celery(request, id_analisis):
    data = serializers.serialize('json', [request.user])
    download_task = comenzar_celery.delay(id_analisis, data)
    task_id = download_task.task_id
    print (f'Creada nueva tarea de celery con task_id={task_id}')
    return JsonResponse({'task_id':task_id})


def get_progress(request, task_id):
    print(f'Buscando estado actual de la tarea de celery {task_id}')
    result = AsyncResult(task_id)
    print("Estado actual:", result.state, ". Informacion actual:", result.info)
    if result.state == 'RETRY':
        response_data = {
        'state': result.state,
        'details': 'Error',
        }
    else:
        response_data = {
            'state': result.state,
            'details': result.info,
        }
    return HttpResponse(json.dumps(response_data), content_type='application/json')


@login_required
def descargar_resultados_clasificador(request, id_analisis):
    analisis = Analisis.objects.get(id = id_analisis)
    usuario_actual = request.user
    if analisis.carpeta.usuario != usuario_actual:
        return HttpResponse("No tiene permiso para descargar este resultado")
    resultados = Resultado.objects.filter(analisis = analisis)
    html = """
    <table class="table">
                            <thead>
                                <tr>
                                <th scope="col">Num Linea</th>
                                <th scope="col">Remitente</th>
                                <th scope="col">Fecha</th>
                                <th scope="col">Texto</th>
                                <th scope="col">Detectado</th>
                                <th scope="col">Archivo</th>
                                </tr>
                            </thead>
                            <tbody>
    """
    for resultado in resultados:
        html += "<div class='col'> <div>"+ resultado.html+"</div> </div>"
        html += """<tr>
                <th scope="row">"""+str(resultado.numero_linea)+"""</th>"""

        if resultado.remitente:
            html += """<td>"""+resultado.remitente+"""</td>"""
        else:
            html += """<td> Desconocido </td>"""
        
        if resultado.fecha_envio:
            html += """<td>"""+str(resultado.fecha_envio)+"""</td>"""
        else:
            html += """<td> - </td>"""
        html += """<td >"""+resultado.texto+"""</td>"""
        if resultado.detectado == "No Violento":
            html += """<td > 
                        <span class="badge category-3 "> """+resultado.detectado+""" </span>
                    </td>"""
        elif resultado.detectado == "Sexual":
            html += """<td > 
                        <span class="badge category-2 "> """+resultado.detectado+""" </span>
                    </td>"""
        elif resultado.detectado == "Físico":
            html += """<td > 
                        <span class="badge category-1 "> """+resultado.detectado+""" </span>
                    </td>"""
        elif resultado.detectado == "Psicológica":
            html += """<td > 
                        <span class="badge category-4 "> """+resultado.detectado+""" </span>
                    </td>"""
        else:
            html += """<td > 
                        <span class="badge category-5 "> """+resultado.detectado+""" </span>
                    </td>"""
        html += """<td>"""+resultado.archivo_origen.nombre+"""</td>
            </tr>
        """
    html += """</tbody>
            </table>"""
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename= "resultados_completos_clasificador.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
            return HttpResponse('We had some errors')
    return response

@login_required
def crear_wordcloud(request, id_analisis):
    usuario_actual = request.user
    analisis = Analisis.objects.get(id = id_analisis)
    preposiciones = [
        'a', 'ante', 'bajo', 'cabe', 'con', 'contra', 'de', 'desde', 'durante', 'en', 'entre', 'hacia', 'hasta', 'mediante', 'para', 'por', 'según', 'sin', 'so', 'sobre', 'tras', 'versus' , 'via'
    ]
    if analisis.carpeta.usuario != usuario_actual:
        return HttpResponse("No tiene permiso para visualizar este analisis")
    if request.method == 'POST':
            form = WordcloudForm(request.POST)
            if form.is_valid():
                
                stopwords = form.cleaned_data['stopwords']
                violentos = form.cleaned_data['violentos']
                excluidas = form.cleaned_data['excluidas']
                excluidas = [word.strip() for word in excluidas.split(',')]
                resultados = Resultado.objects.filter(analisis = analisis)
                if violentos:
                    resultados = resultados.exclude(detectado = 'No Violento')
                texto = [resultado.texto for resultado in resultados]
                texto = ' '.join(texto)
                all_words = texto.split()
                if stopwords:
                    excluidas = excluidas + preposiciones
                if excluidas:
                    new_text = [word for word in all_words if word not in excluidas]
                    cleaned_text  = ' '.join(new_text)
                else: 
                    cleaned_text = texto
                wordcloud = nuevo_wordcloud(cleaned_text)
                
                # Prepare the image for download
                img_stream = io.BytesIO()
                wordcloud.to_image().save(img_stream, format='PNG')
                img_stream.seek(0)

                # Prepare the response for download
                response = HttpResponse(content_type='image/png')
                response['Content-Disposition'] = 'attachment; filename="wordcloud.png"'
                response.write(img_stream.getvalue())
            
                return response
            
    return render(request, "analisis/crear_wordcloud.html", context= {'form': WordcloudForm(), 'id_analisis': id_analisis})

