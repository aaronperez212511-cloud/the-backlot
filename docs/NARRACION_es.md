# Narración en español — lo que dices en voz alta

Esto es **solo el audio**. Los subtítulos van en inglés (`the-backlot-demo.srt`),
porque las reglas exigen inglés en el audio *o* en los subtítulos, y tú vas a
hablar español. Todo lo escrito que aparece en cámara — la consola, el trace,
la terminal — ya está en inglés, que es el otro requisito.

**Cada bloque está medido.** El español necesita más palabras que el inglés para
decir lo mismo, y los beats ya venían justos, así que estos textos están
recortados para caber. El conteo entre paréntesis es el presupuesto real a un
ritmo de lectura normal (~2.5 palabras por segundo). Si improvisas de más, te
comes el beat siguiente.

No leas esto como locución de documental. Habla como quien enseña su sistema a
un colega que sabe del tema.

---

## 0:00–0:20 · Apertura *(48 palabras)*

Pantalla: la consola en reposo, con el panel Watchtower **ya poblado**.

> Midnight Marquee se estrena en cinco minutos. Esta noche pueden fallar seis
> cosas: regalías mal pagadas, un anuncio en blanco, una red de bots, una
> región con buffering, una audiencia que se va. La mayoría de los estudios usa
> seis herramientas separadas, y ninguna le habla a las demás.

## 0:20–1:05 · El incidente *(72 palabras)*

Abre `?ask=1`. Deja correr el spinner unos segundos, señala los dos
especialistas encendiéndose, corta. Abre el trace y desplázalo. **Habla cuando
ya está la respuesta en pantalla**, no antes.

> Dos especialistas, dos dominios, dos síntomas: una sola causa raíz. Ninguno
> pudo haberlo dicho solo — el agente de reproducción no ve ingresos
> publicitarios, y el de anuncios no ve telemetría de CDN. Esa correlación es
> la razón entera de que esto sea una flota y no seis demos.

Y la línea arquitectónica, que es el diferenciador técnico:

> En ADK esto solo funciona porque los especialistas están conectados como
> herramientas que devuelven su hallazgo. Como sub-agentes toman la
> conversación y nunca la devuelven.

## 1:05–1:35 · Chain of Title *(54 palabras)*

Abre `?ask=2`. Muestra la cláusula original, la llamada a Gemini, y la
aritmética.

> Ahora el contrato. Gemini lee la cláusula original y convierte la prosa en
> términos calculables. Unidades a tarifa base, unidades a tarifa escalonada,
> lo esperado contra lo pagado, y la diferencia. Cada número aquí se re-deriva
> del warehouse. Nada es una constante mágica. Eso es contabilidad forense que
> un abogado puede seguir, no un dashboard.

## 1:35–1:58 · Fraude, y contención *(45 palabras)*

Abre `?ask=3`. Señala lo que **no** marca: los hogares legítimos y los
dispositivos de recinto que están en los mismos datos.

> Una huella de dispositivo en noventa cuentas, corroborada por viajes
> imposibles. La red se esconde entre una multitud realista: la dispersión sola
> no es fraude. Y consultó a un especialista, no a seis. Pregunta de un solo
> dominio: el orquestador enruta, no dispara contra todo.

## 1:58–2:25 · El Watchtower *(57 palabras)* — no lo apures

Este es el beat sin holgura. Haz clic en el hallazgo más reciente del panel y
**señala la marca de tiempo**: es anterior a que te sentaras.

> Ese reporte no se escribió para mí. Cloud Scheduler llamó a la flota en
> punto, Control Room corrió un brief permanente, dos especialistas consultaron
> ClickHouse, y archivó una causa raíz con una severidad que se asignó solo,
> sin nadie mirando. Un nodo de CDN no falla a una hora conveniente. El
> disparador es un reloj, no una petición.

## 2:25–2:48 · Prueba, no intuición *(47 palabras)*

Corta a terminal. `python clickhouse/verify_anomalies.py`.

> La verdad base está en el repositorio. Esto verifica cada anomalía sembrada
> contra la base en vivo, incluyendo que los señuelos existen, para que
> detectar no sea trivial. Y el juez de rúbricas de ADK evalúa con veintitrés
> rúbricas. Dos verifican que los agentes no inventen hallazgos.

## 2:48–3:00 · Cierre *(31 palabras)*

Muestra `design/the-backlot-flow.png` tres segundos.

> Seis especialistas, una base de ClickHouse, un orquestador que conecta los
> puntos. Gemini 2.5 en Vertex AI, el ADK, y el servidor MCP oficial de
> ClickHouse. En vivo. Esto es The Backlot.

---

## Cómo encajar los subtítulos después

El `.srt` en inglés está escrito cue por cue contra **estos** bloques, no
contra el guion en inglés — cada cue traduce una frase de arriba. Graba
primero, y en el editor arrastra cada cue hasta donde realmente dijiste esa
frase. Ninguno necesita re-dividirse.

Si un beat se te alarga, el que tiene holgura es **0:20–1:05**: la
investigación corre por debajo de todos modos y puedes cortar más espera. El
que no tiene holgura es **1:58–2:25**, y es el que te distingue del resto del
track.
