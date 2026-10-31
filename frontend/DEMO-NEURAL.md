# Demo neural de xValue

La demo está en `/`. La versión editorial anterior (`/demo-editorial`) y los datos sintéticos de `synthetic-test-data/` se retiraron el 31/10; siguen disponibles en el historial de Git (commit `26afa28`).

La introducción presenta xValue animado, un fondo de conexiones con impulsos de luz y el futbolista holográfico, y tres entradas: Comprar, Vender y Comparar. La intro espera a que se elija una; ya no avanza sola. Después, el mismo recurso visual pasa a un avatar contextual. El producto tiene cuatro pestañas: Comprar, Vender, Comparar y Cómo funciona.

## Datos reales (resultados del modelo)

`/` lee `../data/processed/model_outputs/predicciones_xvalue_final_v1.parquet` (o la ruta de `XVALUE_PREDICTIONS_PARQUET`) en el servidor, con `hyparquet`. Es la única fuente; los parquets anteriores quedan descartados. Columnas usadas: `player_name`, `league`, `club`, `age`, `season`, `pred_fee_eur`, `pred_fee_bajo_eur`, `pred_fee_alto_eur`, `current_mv_eur` (valor de mercado), `xvalue_gap`, `xvalue_gap_bajo` y `xvalue_gap_alto`. `mv_fuente` y `senal_gap` no se usan.

Cada registro es una observación jugador–club–temporada 2025/26: el club es una variable de entrada del modelo, así que el rango estima el traspaso de ese jugador a ese club. No hay `player_id`; la clave del registro se forma con nombre, club y temporada, de modo que no depende del orden de las filas.

- **Rango xValue** (bajo–alto): referencia principal; la estimación central (`pred_fee_eur`) se muestra como cifra secundaria. Desde `predicciones_xvalue_final` el margen del rango cambia por tramos de la estimación central (cinco tramos; inferior entre ÷ 2,6 y ÷ 4,2, superior entre × 2,5 y × 3,2): esos factores los calcula la capa de datos (`lib/predictions/repository.ts`) a partir del archivo; Cómo funciona da una explicación general, sin cifras del archivo.
- **Valor de mercado y xValue Gap**: en la ficha del jugador (Comprar y Vender) y en cada registro de Comparar. El Gap es `xvalue_gap` (estimación central − valor de mercado). Sin valor de mercado solo desaparecen el Gap y la diferencia con el valor de mercado.
- **Comprar**: precio de compra frente al rango (por debajo, dentro o por encima; un límite cuenta como dentro).
- **Vender**: margen bruto = oferta − importe pagado por el traspaso. Sin importe pagado, la oferta frente al rango. El rango no se convierte en margen de reventa.
- **Comparar**: dos registros en una escala común; el solapamiento es contexto, no veredicto; la diferencia de precio depende solo de los precios introducidos.

Los cálculos y textos están en `lib/predictions/scenarios.ts`, sin dependencias, con pruebas en `scenarios.test.ts` (`npm test`). Formato español: M€ con un decimal desde 1 M€; por debajo, euros redondeados a miles; una diferencia distinta de 0 nunca se muestra como 0. Importes admitidos: de 0 a 1.000 M€.

Capas: `lib/predictions/parquet-source.ts` (lectura, caché por fecha de modificación) → `repository.ts` (interfaz `PredictionRepository`, sustituible por DuckDB o una API) → `GET /api/predictions` (búsqueda por jugador, club o liga y paginación en servidor) → `client.ts` → componentes. El navegador recibe páginas de pocos registros, nunca el Parquet.

No existe `player_id`: cada fila es una observación jugador–temporada y un nombre repetido no se trata como la misma persona. Las líneas y la red animada son narrativa de interfaz; no representan el modelo.

## Recurso del futbolista

Archivo final: `public/images/xvalue-footballer.png`.

Modo utilizado: herramienta integrada ImageGen, edición con fondo transparente. Referencia: fotograma inicial del vídeo aportado por el usuario, `WhatsApp Video 2026-10-03 at 19.28.01.mp4`.

El recurso es una adaptación del fotograma. El hero y el avatar comparten el mismo PNG, aplicado a una malla 2D articulada en WebGL. Pesos suaves deforman cabeza, torso, brazos, pierna posterior, pie y balón de forma independiente. Un shader añade impulsos internos. No se incorpora un modelo 3D nuevo. Si WebGL no está disponible, se muestra el recurso estático.

## Segunda iteración: inteligencia viva

- Estados de reposo, bienvenida, atención y explicación; la animación del avatar pequeño está activada y sus gestos se amplían suavemente para su tamaño.
- Red con 360 puntos de conexión en escritorio y 126 en móvil, organizada en núcleos, ramificaciones y filamentos profundos. Los impulsos activan los destinos y se propagan a otras ramas.
- El contacto con el balón dispara una onda y una activación local que también llega a la trama del nombre.
- Eventos compartidos coordinan el personaje, el fondo y los recorridos entre componentes. Las conexiones usan los bordes reales del DOM y se adaptan al tamaño y al desplazamiento.
- Comprar y Vender: jugador → ficha y rango → escenario; la referencia de mercado cuelga de la ficha, nunca del resultado. Comparación: ambos registros → escala común → diferencia de precio. Metodología: del jugador a la estimación → rango → Gap ← valor de mercado → explora tus opciones.
- Con movimiento reducido, la malla y el fondo permanecen estáticos y las relaciones entre componentes conservan sus trazados.

Las conexiones representan las relaciones visualizadas en la demo. Los datos y las fórmulas existentes no se modifican. La implementación utiliza canvas, WebGL y GSAP ya instalado, sin nuevas dependencias de producción.

Prompt utilizado:

```text
Use case: background-extraction. Edit target: the supplied original xValue video frame. Create a genuinely transparent PNG cutout of ONLY the existing full-body luminous cyan footballer and his football. Preserve exactly the player's existing silhouette, body proportions, orientation and distinctive pose: leaning right, left arm extending left, right arm extending right, back leg stretched left, front leg beside ball at lower right. Preserve the same faceless translucent point-cloud wire-network holographic appearance, fine cyan nodes and connecting lines, shorts and football boots. Preserve the original ball design and its position beside the player's front foot. Remove all typography, xValue wordmarks, UI buttons, dark rectangular background, detached background stars, large floating trails and reflected ground. Do not invent a different character, face, pose or outfit. Reconstruct only tiny missing figure edges if needed. Full body and football entirely within canvas, tightly centered with approximately 8% clear transparent padding on each side. Portrait composition. The asset will be used as the exact same recognizable xValue hero and contextual avatar in a website; clean transparent edges, no text, no watermark.
```

## Comprobaciones

- Compilación de producción, TypeScript, ESLint y las pruebas de `npm test` completados sin errores.
- En navegador: entrada desde la intro, las cuatro pestañas, búsqueda de jugador, precio, oferta e importe pagado, comparación con precios, importe no válido y ancho de 375 píxeles sin desbordamiento horizontal.
- Tras la revisión de Codex (26/10): el desplegable del buscador queda por encima de la ficha y recibe los clics; Enter solo elige resultados de la búsqueda vigente; las flechas mantienen visible la opción activa; las conexiones entre columnas de distinta altura van por el hueco entre ellas. Estas comprobaciones son manuales: no hay pruebas automáticas de interacción.
- Iteración del 26/10 (manual, en navegador, salvo lo indicado):
  - Interfaz de trabajo clara tras la intro (la intro sigue oscura): paneles y desplegables opacos y conexiones atenuadas (la placa oscura del avatar se retiró después; véase más abajo).
  - Selector paginado de 20 en 20 con «Cargar más» y contador («Mostrando 20 de 644 registros»). Comprobado: se llega a los 644 registros (32 cargas, orden alfabético, sin duplicados) y al último (Zian Flemming) con el ratón; con «premier» (142) la flecha carga la segunda página y Enter elige la opción 26; cambiar la búsqueda con una página pendiente no mezcla resultados; error y «Reintentar»; exclusión del registro elegido en el otro lado de Comparar (643) y aviso si es el único que coincide.
  - Gráfico del rango: banda gruesa con extremos marcados, «Límite inferior» y «Límite superior» rotulados, importe destacado encima y valor de mercado como referencia secundaria; cada marca en su fila. Comprobado con importes por debajo, iguales a cada límite, dentro, encima y a menos de 120.000 € de un límite: sin etiquetas solapadas ni fuera del gráfico. Comparar comparte una sola escala.
  - A 1280, 768 y 375 px: sin desbordamiento horizontal y ninguna conexión decorativa cruza un panel ni la cabecera (comprobación numérica de 17 recorridos por ancho, con una réplica del cálculo de las curvas).
- Compactación de Comprar y Vender (26/10): sin el bloque «Referencia de mercado» (el valor de mercado queda como rombo en la banda y en la leyenda; el Gap sigue en Comparar y Cómo funciona), cabecera de una línea, avatar pequeño con su mensaje como globo flotante, selector integrado en la ficha, tres columnas (jugador, escenario, gráfico) y etiquetas del gráfico de una línea que comparten fila cuando no chocan. Medido en el navegador con el pie como final del contenido: a 1366×768 el máximo es 659 px (Vender con margen; 743 px con los tres desplegables abiertos), a 1440×900 661 px y a 1920×1080 661 px, en todos los casos con `scrollHeight` = `clientHeight`, sin elementos fuera de pantalla ni etiquetas solapadas. Casos: campos vacíos, por debajo, dentro y encima del rango, margen positivo, negativo y cero, nombre más largo, nombre repetido y valor de mercado. En móvil se desplaza con normalidad.
- Ajuste del 26/10 (decisión del usuario): la estimación central (`pred_fee_eur`) se muestra ya como cifra, porque es la base del xValue Gap. En Comprar y Vender, la ficha lista «Estimación central», «Valor de mercado» y «xValue Gap» (forma corta, sin signo); en el gráfico la central es un círculo sobre la banda, nombrado en la leyenda; en Comparar aparece bajo el rango de cada registro. Se retiraron, a petición del usuario: «Cómo se calcula el rango» y los avisos de la ficha («No es un precio garantizado…»), las notas al pie de Comprar y Vender, «(fecha pendiente)» y «Estimación para su traspaso…» en Comparar, «No se asigna ganador» en su cabecera y la fuente y la nota de animación del pie. A 1366×768 Comprar y Vender terminan como máximo en 599 px.
- Portada, «Cómo funciona» y avatar (26/10):
  - En escritorio (desde 801 px) la portada reparte la altura con `clamp()` en `vh`. Caben la cabecera y el enlace «Cómo funciona», la marca, el título, la descripción, las tres entradas, el futbolista completo con el balón y el pie. El alto del futbolista depende de la altura disponible y mantiene la proporción 2:3 del recurso. No se oculta contenido, no se bloquea el desplazamiento ni se escala la página.
  - «Cómo funciona» compacta separaciones y la redacción de los cinco bloques y de las notas, con el mismo significado y las mismas limitaciones del modelo. El texto queda en 13,5 px y las notas en 12,5 px.
  - El avatar ya no tiene placa: el recurso transparente se ve directamente sobre la interfaz, sin fondo, borde ni sombra. Conserva el tamaño (38 × 56 px), la animación y el foco.
  - Medido en el navegador, con `scrollHeight` = `clientHeight` y sin solapamientos ni elementos fuera de pantalla:
    - Portada: termina en 768 a 1366×768, en 900 a 1440×900 y en 1080 a 1920×1080.
    - «Cómo funciona»: termina en 623, 623 y 604 px respectivamente, sin párrafos recortados.
  - A 375 px ambas se desplazan con normalidad, sin desbordamiento horizontal.
  - El avatar se comprobó sin placa en las cuatro pestañas, hablando y en reposo.
  - Movimiento reducido: revisado solo en el código. `animation: none` deja los elementos en su estado final y se omite el vuelo GSAP.
- **Pendiente: pedir al equipo los nombres originales.** `predicciones_xvalue_final_v1` trae `player_name` en minúsculas y sin tildes («yeremy pino»). Mientras tanto, la interfaz capitaliza la primera letra de cada palabra solo al mostrarlos (`lib/predictions/display.ts`): no añade tildes ni recupera partículas como «de» en «de Jong». Los datos, la búsqueda y la detección de nombres repetidos usan el nombre tal como llega.
- Pendiente de revisar con el panel visible: la transición animada del futbolista al avatar (con el panel oculto el navegador frena las animaciones) y el modo de movimiento reducido.

La propuesta visual toma como referencias la investigación previa de 21st.dev, Paper, React Bits y Magic UI. El fondo y la animación del nombre se implementan en canvas para adaptar el ritmo y la composición a xValue.
