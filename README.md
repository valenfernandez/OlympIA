# OlympIA
## Proyecto final para optar al grado de Ingeniero en Informática

OlympIA es una herramienta de análisis automático de texto para usuarios inexpertos del ámbito judicial.
Permite cargar conversaciones de mensajes de texto y analizarlas utilizando distintos modelos de Inteligencia artificial, generando un reporte donde se visualizan los resultados del analisis.

Este repositorio contiene los datasets recopilados y limpiados para el entrenamiendo de los modelos de NLP. Dichos datasets contienen mensajes principalmente de la zona de Argentina y paises limitrofes. Fueron extraidos de redes sociales y datasets publicos. Estan enfocados en mensajes que contienen distintos tipos de violencia, conteniendo aproximadamente un 50% de mensajes violentos.

Contiene las diferentes iteraciones de entrenamientos de los modelos de NLP: 
* Clasificador de violencia binario: Indica si un texto es violento o no.
* Clasificador de violencia multicategoria: Indica que tipo de violencia esta presente en un texto. Este modelo es utilizado posteriormente al clasificador binario y contempla los tipos de violencia definidos en la ley Argentina.
* Detector de entidades: NER con categorias PERSONA, ORGANIZACIÓN, MEDIDA, TIEMPO, LUGAR, HORA, FECHA, DINERO y MISCELÁNEO.

El contiene ademas el sitio web django que procesa los archivos de texto, sirve de interfaz para la aplicacion de los modelos y genera el reporte con los resultados.


<table>
  <tr>
    <td rowspan="2">
      <img src="https://github.com/user-attachments/assets/a11201ca-eef3-4294-be3b-76cf2fb40fc5" alt="results" width="500">
    </td>
    <td>
      <img src="https://github.com/user-attachments/assets/a926501d-10f3-4a59-aeca-8411b41e0566" alt="report" width="300">
    </td>
  </tr>
  <tr>
    <td>
      <img src="https://github.com/user-attachments/assets/0ad9b6ab-0399-4be8-accb-0c94f45baa16" alt="report2" width="300">
    </td>
  </tr>
</table>

**Autores**

Buendia, Pablo Agustin
buenaspablo@gmail.com

Fernández, Valentina
valen.fernandez.montenegro@gmail.com

**Director**			           
Ing. Bruno Constanzo			

**Co-Director**
Ing. Martín Castellote
