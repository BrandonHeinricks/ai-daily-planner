from flask import Blueprint, render_template_string, request, jsonify
import datetime
import uuid
import storage
from ui import render_layout
from calendar_service import (
    agregar_eventos_al_calendario,
    agregar_evento_fijo_calendario,
    actualizar_evento_calendario,
    eliminar_evento_calendario,
    sincronizar_semana_con_google
)

calendario_bp = Blueprint('calendario', __name__)

CALENDARIO_HTML = """
<div class="calendar-page-layout" id="calendarApp">

    <!-- COLUMNA IZQUIERDA: Minicalendario + Mis Eventos -->
    <aside class="calendar-left-sidebar">
        
        <!-- Minicalendario mensual interactivo -->
        <div class="mini-cal-card">
            <div class="mini-cal-header">
                <span class="mini-cal-title" id="miniCalTitle"></span>
                <div class="mini-cal-nav">
                    <button type="button" class="mini-nav-btn" onclick="cambiarMesMini(-1)" title="Mes anterior">&lt;</button>
                    <button type="button" class="mini-nav-btn" onclick="cambiarMesMini(1)" title="Mes siguiente">&gt;</button>
                </div>
            </div>
            <div class="mini-cal-weekdays">
                <span>D</span><span>L</span><span>M</span><span>X</span><span>J</span><span>V</span><span>S</span>
            </div>
            <div class="mini-cal-days" id="miniCalDays"></div>
        </div>

        <!-- Apartado Mis Eventos -->
        <div class="mis-eventos-section">
            <div class="mis-eventos-header">
                <h3 class="mis-eventos-title">Mis Eventos</h3>
                <button type="button" class="add-event-circle-btn" onclick="abrirModalCrearEvento()" title="Agregar evento">+</button>
            </div>
            
            <div class="mis-eventos-list" id="sidebarEventosList">
                {% if primeros_eventos %}
                    {% for ev in primeros_eventos %}
                        <div class="evento-item">
                            <div class="evento-info">
                                <span class="evento-name">{{ ev.titulo }}</span>
                                <span class="evento-date">{{ ev.etiqueta_lateral }}</span>
                            </div>
                            <button type="button" class="evento-del-mini" onclick="eliminarEventoFijo('{{ ev.id }}')" title="Borrar evento">✕</button>
                        </div>
                    {% endfor %}
                {% else %}
                    <div class="evento-empty">Sin eventos próximos</div>
                {% endif %}
            </div>

            <button type="button" id="moreEventsDotsBtn" class="more-events-dots" 
                    style="display: {{ 'block' if hay_mas_eventos else 'none' }};"
                    onclick="abrirModalEventos()" title="Ver todos los eventos">
                •••
            </button>
        </div>

    </aside>

    <!-- COLUMNA DERECHA: Calendario Principal -->
    <div class="section-card calendar-wrapper">
        
        <!-- Controles superiores -->
        <div class="cal-toolbar">
            <div class="cal-date-title" id="mainDateTitle">{{ mes_actual }} {{ anio_actual }}</div>
            
            <!-- Toggle Switch: Semana / Día -->
            <div class="view-toggle">
                <span id="labelSemana" class="active">Semana</span>
                <label class="switch">
                    <input type="checkbox" id="toggleViewBtn" onchange="switchView()">
                    <span class="slider"></span>
                </label>
                <span id="labelDia">Día</span>
            </div>
        </div>

        <!-- Cabecera de días (X-axis) -->
        <div class="cal-header-grid" id="calHeaderGrid">
            <div class="gmt-label"></div>
            {% for dia in semana_datos %}
                <div class="day-header {% if dia.es_hoy %}is-today{% endif %}" data-header-date="{{ dia.fecha_iso }}">
                    <div class="day-name">{{ dia.nombre }}</div>
                    <div class="day-number {% if dia.es_hoy %}current-day-circle{% endif %}">{{ dia.numero }}</div>
                </div>
            {% endfor %}
        </div>

        <!-- Cuerpo desplazable del calendario -->
        <div class="cal-scroll-area" id="calScrollArea">
            <div class="cal-body-grid" id="calBodyGrid">
                
                <!-- Columna de horas -->
                <div class="time-labels">
                    {% for hora in horas_etiquetas %}
                        <div class="time-slot-label"><span>{{ hora }}</span></div>
                    {% endfor %}
                </div>

                <!-- Columnas de los días -->
                <div class="days-container" id="daysContainerMain">
                    <!-- Línea de tiempo actual -->
                    <div class="current-time-line" style="top: {{ linea_roja_top }}px;"></div>
                    
                    {% for dia in semana_datos %}
                        <div class="day-column {% if dia.es_hoy %}is-today-col{% endif %}" data-date="{{ dia.fecha_iso }}">
                            {% for _ in range(24) %}
                                <div class="grid-cell"></div>
                            {% endfor %}
                            
                            {% for bloque in dia.bloques %}
                                <div class="task-block {% if bloque.es_evento %}event-immutable{% endif %} {% if bloque.completado %}completed{% endif %} {% if bloque.height < 45 %}is-tiny{% endif %}" 
                                     data-index="{{ bloque.task_index }}"
                                     data-es-evento="{{ 'true' if bloque.es_evento else 'false' }}"
                                     data-top="{{ bloque.top }}"
                                     data-height="{{ bloque.height }}"
                                     data-title="{{ bloque.tarea }}"
                                     data-type="{{ bloque.tipo }}"
                                     data-start="{{ bloque.hora_inicio }}"
                                     data-end="{{ bloque.hora_fin }}"
                                     data-completed="{{ 'true' if bloque.completado else 'false' }}"
                                     style="top: {{ bloque.top }}px; height: {{ bloque.height }}px;">
                                    <strong class="task-time-label">{{ bloque.hora_inicio }} - {{ bloque.hora_fin }}</strong>
                                    <span class="task-title-label">{{ bloque.tarea }}</span>
                                    <small class="task-type-badge">{{ 'EVENTO FIJO' if bloque.es_evento else bloque.tipo }}</small>
                                </div>
                            {% endfor %}
                        </div>
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>

</div>

<!-- Modales -->
<div id="creationModalOverlay" class="blur-overlay">
    <div class="sketch-modal-card">
        <form id="createTaskForm" onsubmit="confirmarNuevaTarea(event)">
            <div class="sketch-modal-row">
                <input type="text" id="inputTaskName" class="sketch-pill-input" placeholder="nombre:" required autocomplete="off">
                <div class="sketch-select-wrapper">
                    <select id="inputTaskType" class="sketch-select">
                        <option value="estudio" selected>Tipo</option>
                        <option value="estudio">Estudio</option>
                        <option value="trabajo">Trabajo</option>
                        <option value="gym">Gym</option>
                    </select>
                </div>
            </div>
            <button type="submit" style="display:none;"></button>
        </form>
    </div>
</div>

<div id="editModalOverlay" class="blur-overlay">
    <div class="sketch-edit-card">
        <form id="editTaskForm" onsubmit="guardarEdicionTarea(event)">
            <div class="sketch-edit-header">
                <h3 id="editHeaderTitle" class="sketch-edit-title">Tarea</h3>
                <label class="sketch-check-label" title="Marcar como completada">
                    <input type="checkbox" id="editTaskCompleted" class="sketch-checkbox">
                    <span>Hecha</span>
                </label>
            </div>
            <hr class="sketch-divider">
            <div class="sketch-modal-row edit-middle-row">
                <input type="text" id="editTaskName" class="sketch-pill-input" placeholder="nombre" required autocomplete="off"
                       oninput="document.getElementById('editHeaderTitle').innerText = this.value || 'Tarea'">
                <div class="sketch-select-wrapper">
                    <select id="editTaskType" class="sketch-select">
                        <option value="estudio">Estudio</option>
                        <option value="trabajo">Trabajo</option>
                        <option value="gym">Gym</option>
                    </select>
                </div>
            </div>
            <div class="sketch-time-row">
                <div class="sketch-time-group">
                    <label for="editTaskStart">inicio:</label>
                    <input type="text" id="editTaskStart" class="sketch-time-pill" placeholder="09:00" maxlength="5" required>
                </div>
                <div class="sketch-time-group">
                    <label for="editTaskFin">fin:</label>
                    <input type="text" id="editTaskFin" class="sketch-time-pill" placeholder="10:30" maxlength="5" required>
                </div>
            </div>
            <div class="sketch-edit-footer">
                <span id="editErrorMsg" class="sketch-error-msg"></span>
                <button type="button" class="sketch-trash-btn" onclick="eliminarTareaActual()" title="Eliminar tarea">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                </button>
            </div>
            <button type="submit" style="display:none;"></button>
        </form>
    </div>
</div>

<div id="createEventModalOverlay" class="blur-overlay">
    <div class="sketch-event-create-card">
        <form id="createEventForm" onsubmit="guardarNuevoEvento(event)">
            <div class="event-top-name-wrap">
                <input type="text" id="newEventName" class="event-top-name-input" placeholder="nombre" required autocomplete="off">
            </div>
            <hr class="sketch-divider">
            <div class="event-body-grid">
                <div class="event-left-times">
                    <div class="event-time-line">
                        <label for="newEventStart">inicio:</label>
                        <input type="text" id="newEventStart" class="sketch-time-pill" placeholder="(hh:mm)" maxlength="5" required>
                    </div>
                    <div class="event-time-line">
                        <label for="newEventEnd">fin</label>
                        <input type="text" id="newEventEnd" class="sketch-time-pill" placeholder="(hh:mm)" maxlength="5">
                    </div>
                    <div class="event-time-line">
                        <label for="newEventDate">fecha:</label>
                        <input type="date" id="newEventDate" class="sketch-date-pill" value="{{ hoy_iso }}" required>
                    </div>
                </div>
                <div class="event-right-repeat">
                    <span class="repeat-label">Se Repite</span>
                    <select id="newEventRepeat" class="sketch-select repeat-select">
                        <option value="none" selected>Nunca</option>
                        <option value="daily">Diariamente</option>
                        <option value="weekly">Semanalmente</option>
                        <option value="monthly">Mensualmente</option>
                        <option value="yearly">Cada año</option>
                    </select>
                </div>
            </div>
            <div class="sketch-edit-footer" style="margin-top: 14px;">
                <span id="createEventErrorMsg" class="sketch-error-msg"></span>
                <button type="submit" class="sketch-save-pill-btn">Guardar</button>
            </div>
        </form>
    </div>
</div>

<div id="eventsModalOverlay" class="blur-overlay">
    <div class="sketch-events-modal-card">
        <div class="sketch-edit-header">
            <h3 class="sketch-edit-title">Mis Eventos</h3>
            <button type="button" class="sketch-close-btn" onclick="cerrarModalEventos()">✕</button>
        </div>
        <hr class="sketch-divider">
        <div class="all-events-scroll-list" id="modalAllEventosList">
            {% for ev in todos_eventos %}
                <div class="all-events-row">
                    <div class="all-events-info">
                        <span class="all-events-name">{{ ev.titulo }}</span>
                        <span class="all-events-date">{{ ev.fecha_larga }} · {{ ev.hora_inicio }} ({{ ev.repite_label }})</span>
                    </div>
                    <button type="button" class="sketch-trash-btn" onclick="eliminarEventoFijo('{{ ev.id }}')" title="Borrar evento">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="3 6 5 6 21 6"></polyline>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                        </svg>
                    </button>
                </div>
            {% endfor %}
        </div>
    </div>
</div>

<script>
    const MESES_NOMBRES = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ];
    
    let miniYear = {{ anio_actual }};
    let miniMonth = {{ mes_num - 1 }};
    let fechaSeleccionadaIso = "{{ hoy_iso }}";

    function renderMiniCalendar() {
        const titleEl = document.getElementById('miniCalTitle');
        const daysContainer = document.getElementById('miniCalDays');
        if (!titleEl || !daysContainer) return;

        titleEl.innerText = `${MESES_NOMBRES[miniMonth]} de ${miniYear}`;
        daysContainer.innerHTML = '';

        const firstDayWeek = new Date(miniYear, miniMonth, 1).getDay();
        const daysInMonth = new Date(miniYear, miniMonth + 1, 0).getDate();
        const daysInPrevMonth = new Date(miniYear, miniMonth, 0).getDate();

        // Días mes anterior (inactivos o navegan al mes)
        for (let i = firstDayWeek - 1; i >= 0; i--) {
            const span = document.createElement('span');
            span.className = 'mini-day other-month';
            span.innerText = daysInPrevMonth - i;
            daysContainer.appendChild(span);
        }

        // Días mes actual (CLICABLES)
        for (let d = 1; d <= daysInMonth; d++) {
            const span = document.createElement('span');
            span.className = 'mini-day clickable';
            
            const mStr = String(miniMonth + 1).padStart(2, '0');
            const dStr = String(d).padStart(2, '0');
            const thisIso = `${miniYear}-${mStr}-${dStr}`;

            if (thisIso === fechaSeleccionadaIso) {
                span.classList.add('is-selected-day');
            }

            const hoyStr = new Date().toISOString().split('T')[0];
            if (thisIso === hoyStr) {
                span.classList.add('is-today-bold');
            }

            span.innerText = d;
            span.onclick = () => seleccionarFechaMinicalendario(thisIso);
            daysContainer.appendChild(span);
        }

        const totalCells = daysContainer.children.length;
        const remaining = 42 - totalCells;
        for (let i = 1; i <= remaining; i++) {
            const span = document.createElement('span');
            span.className = 'mini-day other-month';
            span.innerText = i;
            daysContainer.appendChild(span);
        }
    }

    async function seleccionarFechaMinicalendario(isoStr) {
        fechaSeleccionadaIso = isoStr;
        renderMiniCalendar();

        // Forzar vista Diaria automáticamente al hacer clic en un día del minicalendario
        const toggleBtn = document.getElementById('toggleViewBtn');
        if (toggleBtn && !toggleBtn.checked) {
            toggleBtn.checked = true;
            switchView();
        }

        await sincronizarEnSegundoPlano(isoStr);
    }

    function cambiarMesMini(delta) {
        miniMonth += delta;
        if (miniMonth < 0) {
            miniMonth = 11;
            miniYear--;
        } else if (miniMonth > 11) {
            miniMonth = 0;
            miniYear++;
        }
        renderMiniCalendar();
    }

    function abrirModalCrearEvento() {
        document.getElementById('newEventName').value = '';
        document.getElementById('newEventStart').value = '09:00';
        document.getElementById('newEventEnd').value = '09:30';
        document.getElementById('newEventDate').value = fechaSeleccionadaIso;
        document.getElementById('newEventRepeat').value = 'none';
        document.getElementById('createEventErrorMsg').innerText = '';

        document.getElementById('createEventModalOverlay').classList.add('active');
        document.getElementById('newEventName').focus();
    }

    function cerrarModalCrearEvento() {
        document.getElementById('createEventModalOverlay').classList.remove('active');
    }

    async function guardarNuevoEvento(e) {
        if (e) e.preventDefault();
        const titulo = document.getElementById('newEventName').value.trim();
        const rawStart = document.getElementById('newEventStart').value.trim();
        let rawEnd = document.getElementById('newEventEnd').value.trim();
        const fecha = document.getElementById('newEventDate').value;
        const repite = document.getElementById('newEventRepeat').value;
        const errEl = document.getElementById('createEventErrorMsg');

        if (!titulo) return;
        const startMin = timeStrToMin(rawStart);
        if (startMin === null) {
            errEl.innerText = 'Hora de inicio inválida (HH:MM)';
            return;
        }
        let endMin = rawEnd ? timeStrToMin(rawEnd) : Math.min(1439, startMin + 30);
        if (endMin === null || endMin <= startMin) endMin = Math.min(1439, startMin + 30);

        cerrarModalCrearEvento();
        const res = await fetch('/calendario/crear_evento', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ titulo, fecha, hora_inicio: minToTimeStr(startMin), hora_fin: minToTimeStr(endMin), repite })
        });
        if (res.ok) await sincronizarEnSegundoPlano(fechaSeleccionadaIso);
    }

    async function eliminarEventoFijo(eventoId) {
        const res = await fetch('/calendario/eliminar_evento', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: eventoId })
        });
        if (res.ok) await sincronizarEnSegundoPlano(fechaSeleccionadaIso);
    }

    function abrirModalEventos() { document.getElementById('eventsModalOverlay').classList.add('active'); }
    function cerrarModalEventos() { document.getElementById('eventsModalOverlay').classList.remove('active'); }

    window.addEventListener('contextmenu', (e) => {
        if (e.target.closest('#calendarApp') || document.querySelector('.blur-overlay.active')) e.preventDefault();
    });

    function minToTimeStr(mins) {
        const clamped = Math.max(0, Math.min(1439, mins));
        return String(Math.floor(clamped / 60)).padStart(2, '0') + ':' + String(Math.floor(clamped % 60)).padStart(2, '0');
    }

    function timeStrToMin(str) {
        const match = (str || '').trim().match(/^([01]?\\d|2[0-3]):([0-5]\\d)$/);
        return match ? parseInt(match[1], 10) * 60 + parseInt(match[2], 10) : null;
    }

    function isDailyView() { return document.getElementById('toggleViewBtn').checked; }

    function switchView() {
        const isDaily = isDailyView();
        const headers = document.querySelectorAll('.day-header');
        const columns = document.querySelectorAll('.day-column');
        
        document.getElementById('labelSemana').classList.toggle('active', !isDaily);
        document.getElementById('labelDia').classList.toggle('active', isDaily);

        headers.forEach((h, index) => {
            if (isDaily) {
                const hDate = h.dataset.headerDate;
                const matchDay = (hDate === fechaSeleccionadaIso);
                h.style.display = matchDay ? 'flex' : 'none';
                columns[index].style.display = matchDay ? 'block' : 'none';
            } else {
                h.style.display = 'flex';
                columns[index].style.display = 'block';
            }
        });
    }

    let isSyncing = false;

    function actualizarListasEventosDOM(todosEventos) {
        const sidebarList = document.getElementById('sidebarEventosList');
        const modalList = document.getElementById('modalAllEventosList');
        const dotsBtn = document.getElementById('moreEventsDotsBtn');
        if (!sidebarList || !modalList) return;

        const primeros = todosEventos.slice(0, 5);
        sidebarList.innerHTML = '';
        if (primeros.length === 0) {
            sidebarList.innerHTML = '<div class="evento-empty">Sin eventos próximos</div>';
        } else {
            primeros.forEach(ev => {
                const row = document.createElement('div');
                row.className = 'evento-item';
                row.innerHTML = `<div class="evento-info"><span class="evento-name"></span><span class="evento-date"></span></div><button type="button" class="evento-del-mini" title="Borrar">✕</button>`;
                row.querySelector('.evento-name').innerText = ev.titulo;
                row.querySelector('.evento-date').innerText = ev.etiqueta_lateral;
                row.querySelector('.evento-del-mini').onclick = () => eliminarEventoFijo(ev.id);
                sidebarList.appendChild(row);
            });
        }
        if (dotsBtn) dotsBtn.style.display = todosEventos.length > 5 ? 'block' : 'none';

        modalList.innerHTML = '';
        todosEventos.forEach(ev => {
            const item = document.createElement('div');
            item.className = 'all-events-row';
            item.innerHTML = `<div class="all-events-info"><span class="all-events-name"></span><span class="all-events-date"></span></div><button type="button" class="sketch-trash-btn" title="Borrar"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg></button>`;
            item.querySelector('.all-events-name').innerText = ev.titulo;
            item.querySelector('.all-events-date').innerText = `${ev.fecha_larga} · ${ev.hora_inicio} (${ev.repite_label})`;
            item.querySelector('.sketch-trash-btn').onclick = () => eliminarEventoFijo(ev.id);
            modalList.appendChild(item);
        });
    }

    async function sincronizarEnSegundoPlano(targetIso = fechaSeleccionadaIso) {
        if (isSyncing || draggingBlock || isSelectingRightClick) return;
        isSyncing = true;
        try {
            const res = await fetch(`/calendario/datos_semana?fecha=${targetIso}`);
            if (!res.ok) return;
            const data = await res.json();

            document.getElementById('mainDateTitle').innerText = data.mes_anio_titulo;

            const redLine = document.querySelector('.current-time-line');
            if (redLine && data.linea_roja_top !== undefined) redLine.style.top = data.linea_roja_top + 'px';

            if (data.eventos_lista) actualizarListasEventosDOM(data.eventos_lista);

            const daysContainer = document.getElementById('daysContainerMain');
            const headerGrid = document.getElementById('calHeaderGrid');
            
            // Reconstruir cabeceras y columnas con la nueva semana centrada en el día pinchado
            headerGrid.innerHTML = '<div class="gmt-label"></div>';
            daysContainer.innerHTML = '<div class="current-time-line" style="top: ' + (data.linea_roja_top || 0) + 'px;"></div>';

            data.semana_datos.forEach(dia => {
                const hDiv = document.createElement('div');
                hDiv.className = 'day-header' + (dia.es_hoy ? ' is-today' : '');
                hDiv.dataset.headerDate = dia.fecha_iso;
                hDiv.innerHTML = `<div class="day-name">${dia.nombre}</div><div class="day-number ${dia.es_hoy ? 'current-day-circle' : ''}">${dia.numero}</div>`;
                headerGrid.appendChild(hDiv);

                const col = document.createElement('div');
                col.className = 'day-column' + (dia.es_hoy ? ' is-today-col' : '');
                col.dataset.date = dia.fecha_iso;

                for (let c = 0; c < 24; c++) {
                    const cell = document.createElement('div');
                    cell.className = 'grid-cell';
                    col.appendChild(cell);
                }

                dia.bloques.forEach(bloque => {
                    const block = document.createElement('div');
                    block.className = 'task-block' +
                        (bloque.es_evento ? ' event-immutable' : '') +
                        (bloque.completado ? ' completed' : '') +
                        (bloque.height < 45 ? ' is-tiny' : '');
                    
                    block.dataset.index = bloque.task_index;
                    block.dataset.esEvento = bloque.es_evento ? 'true' : 'false';
                    block.dataset.top = bloque.top;
                    block.dataset.height = bloque.height;
                    block.dataset.title = bloque.tarea;
                    block.dataset.type = bloque.tipo;
                    block.dataset.start = bloque.hora_inicio;
                    block.dataset.end = bloque.hora_fin;
                    block.dataset.completed = bloque.completado ? 'true' : 'false';
                    block.style.top = bloque.top + 'px';
                    block.style.height = bloque.height + 'px';

                    block.innerHTML = `
                        <strong class="task-time-label">${bloque.hora_inicio} - ${bloque.hora_fin}</strong>
                        <span class="task-title-label">${bloque.tarea}</span>
                        <small class="task-type-badge">${bloque.es_evento ? 'EVENTO FIJO' : bloque.tipo}</small>
                    `;
                    col.appendChild(block);
                });
                daysContainer.appendChild(col);
            });

            switchView();
            inicializarInteraccionBloques();
            inicializarCreacionDerecho();
        } catch (err) {
            console.error('Error sincronizando:', err);
        } finally {
            isSyncing = false;
        }
    }

    // Funciones de interacción de bloques y creación con clic derecho
    let draggingBlock = null;
    let dragStartY = 0;
    let blockInitialTop = 0;
    let dragHasMoved = false;
    let dragWalls = { minTop: 0, maxTop: 1440 };

    function inicializarInteraccionBloques() {
        document.querySelectorAll('.task-block').forEach(block => {
            if (block.dataset.initialized) return;
            block.dataset.initialized = "true";

            if (block.dataset.esEvento === 'true' || block.classList.contains('event-immutable')) return;

            block.addEventListener('mousedown', (e) => {
                if (e.button !== 0) return;
                e.stopPropagation();
                draggingBlock = block;
                dragStartY = e.clientY;
                blockInitialTop = parseFloat(block.dataset.top);
                dragHasMoved = false;
                const column = block.closest('.day-column');
                dragWalls = obtenerMurosParaBloque(column, block);
                block.classList.add('dragging');
                document.body.style.userSelect = 'none';
            });

            block.addEventListener('dblclick', (e) => {
                e.stopPropagation();
                abrirModalEdicion(block);
            });
        });
    }

    function inicializarCreacionDerecho() {
        document.querySelectorAll('.day-column').forEach(column => {
            if (column.dataset.rightClickInit) return;
            column.dataset.rightClickInit = "true";

            column.addEventListener('mousedown', (e) => {
                if (e.button !== 2 || !isDailyView()) return;
                if (e.target.closest('.task-block')) return;

                e.preventDefault();
                const rect = column.getBoundingClientRect();
                const clickY = Math.round(e.clientY - rect.top);

                selectionWalls = obtenerMurosParaPunto(column, clickY);
                if (selectionWalls.maxBottom - selectionWalls.minTop < 15) return;

                isSelectingRightClick = true;
                activeSelectionColumn = column;
                selectionStartY = Math.max(selectionWalls.minTop, Math.min(selectionWalls.maxBottom - 15, clickY));
                document.body.style.userSelect = 'none';

                if (selectionGhost) selectionGhost.remove();
                selectionGhost = document.createElement('div');
                selectionGhost.className = 'windows-selection-box';
                const initialHeight = Math.min(30, selectionWalls.maxBottom - selectionStartY);
                selectionGhost.style.top = selectionStartY + 'px';
                selectionGhost.style.height = initialHeight + 'px';
                selectionGhost.innerText = `${minToTimeStr(selectionStartY)} - ${minToTimeStr(selectionStartY + initialHeight)}`;
                column.appendChild(selectionGhost);

                pendingTaskData = { fecha_iso: column.dataset.date, top: selectionStartY, height: initialHeight };
            });
        });
    }

    window.addEventListener('mousemove', (e) => {
        if (draggingBlock) {
            const deltaY = e.clientY - dragStartY;
            if (Math.abs(deltaY) > 2) dragHasMoved = true;
            let newTop = Math.round(blockInitialTop + deltaY);
            newTop = Math.max(dragWalls.minTop, Math.min(dragWalls.maxTop, newTop));
            const height = parseFloat(draggingBlock.dataset.height);
            draggingBlock.style.top = newTop + 'px';
            draggingBlock.dataset.top = newTop;
            
            if (height < 45) draggingBlock.classList.add('is-tiny');
            else draggingBlock.classList.remove('is-tiny');

            const strIni = minToTimeStr(newTop);
            const strFin = minToTimeStr(newTop + height);
            draggingBlock.dataset.start = strIni;
            draggingBlock.dataset.end = strFin;
            const timeLabel = draggingBlock.querySelector('.task-time-label');
            if (timeLabel) timeLabel.innerText = `${strIni} - ${strFin}`;
        }

        if (isSelectingRightClick && selectionGhost) {
            const rect = activeSelectionColumn.getBoundingClientRect();
            let currentY = Math.round(e.clientY - rect.top);
            currentY = Math.max(selectionWalls.minTop, Math.min(selectionWalls.maxBottom, currentY));
            const top = Math.min(selectionStartY, currentY);
            const bottom = Math.max(selectionStartY, currentY);
            const height = Math.max(bottom - top, 15);
            const clampedHeight = Math.min(height, selectionWalls.maxBottom - top);

            selectionGhost.style.top = top + 'px';
            selectionGhost.style.height = clampedHeight + 'px';
            selectionGhost.innerText = `${minToTimeStr(top)} - ${minToTimeStr(top + clampedHeight)}`;
            pendingTaskData.top = top;
            pendingTaskData.height = clampedHeight;
        }
    });

    window.addEventListener('mouseup', async (e) => {
        if (draggingBlock && e.button === 0) {
            const block = draggingBlock;
            draggingBlock = null;
            block.classList.remove('dragging');
            document.body.style.userSelect = '';
            const newTop = parseFloat(block.dataset.top);
            if (!dragHasMoved || newTop === blockInitialTop) return;

            const column = block.closest('.day-column');
            await fetch('/calendario/mover_tarea', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ fecha_iso: column.dataset.date, index: parseInt(block.dataset.index), hora_inicio: minToTimeStr(newTop), hora_fin: minToTimeStr(newTop + parseFloat(block.dataset.height)) })
            });
            await sincronizarEnSegundoPlano(fechaSeleccionadaIso);
        }

        if (isSelectingRightClick && e.button === 2) {
            isSelectingRightClick = false;
            document.body.style.userSelect = '';
            abrirModalCreacion();
        }
    });

    let isSelectingRightClick = false;
    let selectionStartY = 0;
    let activeSelectionColumn = null;
    let selectionGhost = null;
    let selectionWalls = { minTop: 0, maxBottom: 1440 };
    let pendingTaskData = { fecha_iso: '', top: 0, height: 30 };

    function obtenerMurosParaBloque(column, currentBlock) {
        let minTop = 0, maxBottom = 1440;
        const currentTop = parseFloat(currentBlock.dataset.top);
        const currentHeight = parseFloat(currentBlock.dataset.height);
        const currentBottom = currentTop + currentHeight;

        column.querySelectorAll('.task-block').forEach(b => {
            if (b === currentBlock) return;
            const bTop = parseFloat(b.dataset.top);
            const bBottom = bTop + parseFloat(b.dataset.height);
            if (bBottom <= currentTop && bBottom > minTop) minTop = bBottom;
            if (bTop >= currentBottom && bTop < maxBottom) maxBottom = bTop;
        });
        return { minTop, maxTop: maxBottom - currentHeight };
    }

    function obtenerMurosParaPunto(column, clickY) {
        let minTop = 0, maxBottom = 1440;
        column.querySelectorAll('.task-block').forEach(b => {
            const bTop = parseFloat(b.dataset.top);
            const bBottom = bTop + parseFloat(b.dataset.height);
            if (bBottom <= clickY && bBottom > minTop) minTop = bBottom;
            if (bTop >= clickY && bTop < maxBottom) maxBottom = bTop;
        });
        return { minTop, maxBottom };
    }

    function haySolapamientoEnColumna(column, ignoreBlock, startMin, endMin) {
        for (const b of column.querySelectorAll('.task-block')) {
            if (b === ignoreBlock) continue;
            const bStart = parseFloat(b.dataset.top);
            const bEnd = bStart + parseFloat(b.dataset.height);
            if (startMin < bEnd && endMin > bStart) return true;
        }
        return false;
    }

    function abrirModalCreacion() {
        const overlay = document.getElementById('creationModalOverlay');
        overlay.classList.add('active');
        document.getElementById('inputTaskName').value = '';
        document.getElementById('inputTaskType').selectedIndex = 0;
        document.getElementById('inputTaskName').focus();
    }
    function cerrarModalCreacion() { document.getElementById('creationModalOverlay').classList.remove('active'); if (selectionGhost) { selectionGhost.remove(); selectionGhost = null; } }

    async function confirmarNuevaTarea(e) {
        if (e) e.preventDefault();
        const nombre = document.getElementById('inputTaskName').value.trim();
        const tipo = document.getElementById('inputTaskType').value || 'estudio';
        if (!nombre) return;
        cerrarModalCreacion();
        await fetch('/calendario/crear_tarea', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fecha_iso: pendingTaskData.fecha_iso, hora_inicio: minToTimeStr(pendingTaskData.top), hora_fin: minToTimeStr(pendingTaskData.top + pendingTaskData.height), tarea: nombre, tipo })
        });
        await sincronizarEnSegundoPlano(fechaSeleccionadaIso);
    }

    let activeEditBlock = null;
    let activeEditColumn = null;

    function abrirModalEdicion(block) {
        activeEditBlock = block;
        activeEditColumn = block.closest('.day-column');
        document.getElementById('editHeaderTitle').innerText = block.dataset.title || 'Tarea';
        document.getElementById('editTaskName').value = block.dataset.title || '';
        document.getElementById('editTaskType').value = block.dataset.type || 'estudio';
        document.getElementById('editTaskStart').value = block.dataset.start || '09:00';
        document.getElementById('editTaskFin').value = block.dataset.end || '10:00';
        document.getElementById('editTaskCompleted').checked = (block.dataset.completed === 'true');
        document.getElementById('editErrorMsg').innerText = '';
        document.getElementById('editModalOverlay').classList.add('active');
        document.getElementById('editTaskName').focus();
    }
    function cerrarModalEdicion() { document.getElementById('editModalOverlay').classList.remove('active'); activeEditBlock = null; activeEditColumn = null; }

    async function guardarEdicionTarea(e) {
        if (e) e.preventDefault();
        if (!activeEditBlock || !activeEditColumn) return;
        const nombre = document.getElementById('editTaskName').value.trim();
        const tipo = document.getElementById('editTaskType').value;
        const startMin = timeStrToMin(document.getElementById('editTaskStart').value.trim());
        const endMin = timeStrToMin(document.getElementById('editTaskFin').value.trim());
        const completado = document.getElementById('editTaskCompleted').checked;
        const errorEl = document.getElementById('editErrorMsg');

        if (startMin === null || endMin === null) { errorEl.innerText = 'Usa formato militar HH:MM'; return; }
        if (endMin <= startMin) { errorEl.innerText = 'La hora fin debe ser mayor al inicio'; return; }
        if (haySolapamientoEnColumna(activeEditColumn, activeEditBlock, startMin, endMin)) { errorEl.innerText = 'Horario ocupado'; return; }

        const fechaIso = activeEditColumn.dataset.date;
        const idx = parseInt(activeEditBlock.dataset.index);
        cerrarModalEdicion();
        await fetch('/calendario/editar_tarea', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fecha_iso: fechaIso, index: idx, tarea: nombre, tipo, hora_inicio: minToTimeStr(startMin), hora_fin: minToTimeStr(endMin), completado })
        });
        await sincronizarEnSegundoPlano(fechaSeleccionadaIso);
    }

    async function eliminarTareaActual() {
        if (!activeEditBlock || !activeEditColumn) return;
        const fechaIso = activeEditColumn.dataset.date;
        const idx = parseInt(activeEditBlock.dataset.index);
        cerrarModalEdicion();
        await fetch('/calendario/eliminar_tarea', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fecha_iso: fechaIso, index: idx })
        });
        await sincronizarEnSegundoPlano(fechaSeleccionadaIso);
    }

    window.addEventListener('DOMContentLoaded', () => {
        renderMiniCalendar();
        inicializarInteraccionBloques();
        inicializarCreacionDerecho();
        
        if (sessionStorage.getItem('calViewMode') === 'daily') {
            document.getElementById('toggleViewBtn').checked = true;
            switchView();
        }
        document.getElementById('toggleViewBtn').addEventListener('change', (e) => {
            sessionStorage.setItem('calViewMode', e.target.checked ? 'daily' : 'weekly');
        });

        const scrollArea = document.getElementById('calScrollArea');
        const redLineTop = {{ linea_roja_top }};
        if (scrollArea) scrollArea.scrollTop = Math.max(0, redLineTop - (scrollArea.clientHeight / 2));
        setInterval(() => sincronizarEnSegundoPlano(fechaSeleccionadaIso), 15000);
    });
</script>
"""
def _formatear_eventos_para_vista():
    meses_cortos = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    meses_largos = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mapa_repite = {
        "none": "Una vez",
        "daily": "Diario",
        "weekly": "Semanal",
        "monthly": "Mensual",
        "yearly": "Anual"
    }
    eventos_crudos = storage.cargar_eventos()
    eventos_formateados = []

    for ev in eventos_crudos:
        fecha_mostrar = ev.get("proxima_fecha", ev.get("fecha", ""))
        repite = ev.get("repite", "none")
        repite_label = mapa_repite.get(repite, "Una vez")
        try:
            dt = datetime.date.fromisoformat(fecha_mostrar)
            fecha_corta = f"{dt.day} {meses_cortos[dt.month]}"
            fecha_larga = f"{dt.day} de {meses_largos[dt.month]} de {dt.year}"
        except Exception:
            fecha_corta = fecha_mostrar
            fecha_larga = fecha_mostrar

        if repite == "daily":
            etiqueta_lateral = f"Diario · {ev.get('hora_inicio', '09:00')}"
        else:
            etiqueta_lateral = f"{fecha_corta} · {ev.get('hora_inicio', '09:00')}"

        eventos_formateados.append({
            "id": ev.get("id"),
            "titulo": ev.get("titulo", "Evento"),
            "fecha": fecha_mostrar,
            "hora_inicio": ev.get("hora_inicio", "09:00"),
            "hora_fin": ev.get("hora_fin", "09:30"),
            "repite": repite,
            "repite_label": repite_label,
            "etiqueta_lateral": etiqueta_lateral,
            "fecha_corta": fecha_corta,
            "fecha_larga": fecha_larga
        })

    return eventos_formateados

def _construir_semana_datos(referencia_date=None, sincronizar=True):
    ahora = datetime.datetime.now()
    hoy_date = ahora.date()
    ref_date = referencia_date if referencia_date else hoy_date
    linea_roja_top = ahora.hour * 60 + ahora.minute if ref_date == hoy_date else 0
    
    nombres_dias = ["LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB", "DOM"]
    meses = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    
    # Calcular la semana centrada en la fecha de referencia
    inicio_semana = ref_date - datetime.timedelta(days=ref_date.weekday())
    
    if sincronizar and ref_date == hoy_date:
        sincronizar_semana_con_google(inicio_semana)
        
    historial = storage.cargar_historial()
    
    semana_datos = []
    for i in range(7):
        d_actual = inicio_semana + datetime.timedelta(days=i)
        d_iso = d_actual.isoformat()
        es_hoy = (d_actual == hoy_date)
        
        tareas_brutas = storage.TAREAS_HOY if es_hoy else historial.get(d_iso, {}).get("tareas", [])
        eventos_fijos_dia = storage.obtener_eventos_del_dia(d_iso)
        bloques_procesados = []
        
        for idx_real, t in enumerate(tareas_brutas):
            try:
                h_ini, m_ini = map(int, t['hora_inicio'].split(':'))
                h_fin, m_fin = map(int, t['hora_fin'].split(':'))
                top_px = h_ini * 60 + m_ini
                height_px = max((h_fin * 60 + m_fin) - top_px, 15)
                t_proc = t.copy()
                t_proc['top'] = top_px
                t_proc['height'] = height_px
                t_proc['es_evento'] = False
                t_proc['task_index'] = idx_real
                bloques_procesados.append(t_proc)
            except Exception:
                pass

        for ev in eventos_fijos_dia:
            try:
                h_ini, m_ini = map(int, ev['hora_inicio'].split(':'))
                h_fin, m_fin = map(int, ev['hora_fin'].split(':'))
                top_px = h_ini * 60 + m_ini
                height_px = max((h_fin * 60 + m_fin) - top_px, 15)
                ev_proc = ev.copy()
                ev_proc['top'] = top_px
                ev_proc['height'] = height_px
                ev_proc['es_evento'] = True
                ev_proc['task_index'] = -1
                bloques_procesados.append(ev_proc)
            except Exception:
                pass

        bloques_procesados.sort(key=lambda x: x['top'])
        semana_datos.append({
            "fecha_iso": d_iso,
            "nombre": nombres_dias[d_actual.weekday()],
            "numero": d_actual.day,
            "es_hoy": es_hoy,
            "bloques": bloques_procesados
        })
        
    mes_titulo = f"{meses[ref_date.month]} {ref_date.year}"
    return semana_datos, linea_roja_top, mes_titulo

@calendario_bp.route('/calendario/datos_semana')
def datos_semana_json():
    fecha_str = request.args.get('fecha')
    ref_date = datetime.date.fromisoformat(fecha_str) if fecha_str else datetime.date.today()
    semana_datos, linea_roja_top, mes_titulo = _construir_semana_datos(referencia_date=ref_date, sincronizar=(ref_date == datetime.date.today()))
    dias_dict = {dia["fecha_iso"]: dia["bloques"] for dia in semana_datos}
    todos_eventos = _formatear_eventos_para_vista()
    return jsonify({
        "linea_roja_top": linea_roja_top,
        "mes_anio_titulo": mes_titulo,
        "dias": dias_dict,
        "semana_datos": semana_datos,
        "eventos_lista": todos_eventos
    })

@calendario_bp.route('/calendario/crear_evento', methods=['POST'])
def crear_evento_fijo():
    data = request.get_json()
    nuevo_evento = {
        "id": f"ev_{uuid.uuid4().hex[:8]}",
        "titulo": data.get('titulo', 'Evento'),
        "fecha": data.get('fecha', datetime.date.today().isoformat()),
        "hora_inicio": data.get('hora_inicio', '09:00'),
        "hora_fin": data.get('hora_fin', '09:30'),
        "repite": data.get('repite', 'none'),
        "google_event_id": None
    }
    try:
        g_id = agregar_evento_fijo_calendario(nuevo_evento)
        if g_id: nuevo_evento["google_event_id"] = g_id
    except Exception as e:
        print(f"⚠️ Error: {e}")
    eventos = storage.cargar_eventos_raw()
    eventos.append(nuevo_evento)
    storage.guardar_eventos_raw(eventos)
    return jsonify({"status": "ok"})

def _obtener_lista_dia(fecha_iso, historial):
    hoy_iso = datetime.date.today().isoformat()
    if fecha_iso == hoy_iso:
        return storage.TAREAS_HOY
    if fecha_iso not in historial:
        historial[fecha_iso] = {"score": 0, "tareas": []}
    return historial[fecha_iso]["tareas"]

def recalcular_dia_historial(fecha_iso):
    """
    Recalcula el porcentaje de rendimiento (score) para cualquier fecha.
    Si es hoy, usa TAREAS_HOY; si es otra fecha, lo busca en history.json.
    """
    hoy_str = datetime.date.today().isoformat()
    
    if fecha_iso == hoy_str:
        storage.recalcular_rendimiento()
        return

    historial = storage.cargar_historial()
    if fecha_iso in historial and "tareas" in historial[fecha_iso]:
        lista = historial[fecha_iso]["tareas"]
        if lista:
            completadas = sum(1 for t in lista if t.get("completado"))
            historial[fecha_iso]["score"] = completadas / len(lista)
        else:
            del historial[fecha_iso]
        storage.guardar_historial(historial)
    
@calendario_bp.route('/calendario/eliminar_evento', methods=['POST'])
def eliminar_evento_fijo_ruta():
    data = request.get_json()
    ev_id = data.get('id')
    eventos = storage.cargar_eventos_raw()
    restantes, evento_borrado = [], None
    for ev in eventos:
        if ev.get('id') == ev_id: evento_borrado = ev
        else: restantes.append(ev)
    storage.guardar_eventos_raw(restantes)
    if evento_borrado and evento_borrado.get("google_event_id"):
        try: eliminar_evento_calendario(evento_borrado["google_event_id"])
        except Exception: pass
    return jsonify({"status": "ok"})

@calendario_bp.route('/calendario/crear_tarea', methods=['POST'])
def crear_tarea_calendario():
    data = request.get_json()
    fecha_iso = data.get('fecha_iso')
    nueva_tarea = {"hora_inicio": data.get('hora_inicio'), "hora_fin": data.get('hora_fin'), "tarea": data.get('tarea'), "tipo": data.get('tipo', 'estudio'), "completado": False, "google_event_id": None}
    try:
        ids = agregar_eventos_al_calendario([nueva_tarea], fecha_iso=fecha_iso)
        if ids: nueva_tarea["google_event_id"] = ids[0]
    except Exception: pass

    hoy_iso = datetime.date.today().isoformat()
    if fecha_iso == hoy_iso:
        storage.TAREAS_HOY.append(nueva_tarea)
        storage.TAREAS_HOY.sort(key=lambda x: x['hora_inicio'])
        storage.recalcular_rendimiento()
    else:
        historial = storage.cargar_historial()
        lista = _obtener_lista_dia(fecha_iso, historial)
        lista.append(nueva_tarea)
        lista.sort(key=lambda x: x['hora_inicio'])
        storage.recalcular_dia_historial(fecha_iso, historial)
        storage.guardar_historial(historial)
    return jsonify({"status": "ok"})

@calendario_bp.route('/calendario/mover_tarea', methods=['POST'])
def mover_tarea_calendario():
    data = request.get_json()
    fecha_iso = data.get('fecha_iso')
    idx = int(data.get('index', -1))
    nueva_ini, nueva_fin = data.get('hora_inicio'), data.get('hora_fin')
    hoy_iso = datetime.date.today().isoformat()
    tarea_objetivo = None

    if fecha_iso == hoy_iso:
        if 0 <= idx < len(storage.TAREAS_HOY):
            tarea_objetivo = storage.TAREAS_HOY[idx]
            tarea_objetivo['hora_inicio'], tarea_objetivo['hora_fin'] = nueva_ini, nueva_fin
            storage.recalcular_rendimiento()
    else:
        historial = storage.cargar_historial()
        lista = _obtener_lista_dia(fecha_iso, historial)
        if 0 <= idx < len(lista):
            tarea_objetivo = lista[idx]
            tarea_objetivo['hora_inicio'], tarea_objetivo['hora_fin'] = nueva_ini, nueva_fin
            storage.guardar_historial(historial)

    if tarea_objetivo:
        try:
            nuevo_id = actualizar_evento_calendario(tarea_objetivo.get("google_event_id"), tarea_objetivo, fecha_iso=fecha_iso)
            if nuevo_id: tarea_objetivo["google_event_id"] = nuevo_id
        except Exception: pass
    return jsonify({"status": "ok"})

@calendario_bp.route('/calendario/editar_tarea', methods=['POST'])
def editar_tarea_calendario():
    data = request.get_json()
    fecha_iso = data.get('fecha_iso')
    idx = int(data.get('index', -1))
    hoy_iso = datetime.date.today().isoformat()
    tarea_objetivo = None

    if fecha_iso == hoy_iso:
        if 0 <= idx < len(storage.TAREAS_HOY):
            t = storage.TAREAS_HOY[idx]
            t['tarea'], t['tipo'], t['hora_inicio'], t['hora_fin'], t['completado'] = data.get('tarea', t['tarea']), data.get('tipo', t.get('tipo', 'estudio')), data.get('hora_inicio', t['hora_inicio']), data.get('hora_fin', t['hora_fin']), bool(data.get('completado', t.get('completado', False)))
            tarea_objetivo = t
    else:
        historial = storage.cargar_historial()
        lista = _obtener_lista_dia(fecha_iso, historial)
        if 0 <= idx < len(lista):
            t = lista[idx]
            t['tarea'], t['tipo'], t['hora_inicio'], t['hora_fin'], t['completado'] = data.get('tarea', t['tarea']), data.get('tipo', t.get('tipo', 'estudio')), data.get('hora_inicio', t['hora_inicio']), data.get('hora_fin', t['hora_fin']), bool(data.get('completado', t.get('completado', False)))
            tarea_objetivo = t

    if tarea_objetivo:
        try:
            nuevo_id = actualizar_evento_calendario(tarea_objetivo.get("google_event_id"), tarea_objetivo, fecha_iso=fecha_iso)
            if nuevo_id: tarea_objetivo["google_event_id"] = nuevo_id
        except Exception: pass

    if fecha_iso == hoy_iso:
        storage.TAREAS_HOY.sort(key=lambda x: x['hora_inicio'])
        storage.recalcular_rendimiento()
    else:
        historial = storage.cargar_historial()
        lista = _obtener_lista_dia(fecha_iso, historial)
        lista.sort(key=lambda x: x['hora_inicio'])
        storage.recalcular_dia_historial(fecha_iso, historial)
        storage.guardar_historial(historial)
    return jsonify({"status": "ok"})

@calendario_bp.route('/calendario/eliminar_tarea', methods=['POST'])
def eliminar_tarea_calendario():
    data = request.get_json()
    fecha_iso = data.get('fecha_iso')
    idx = int(data.get('index', -1))
    hoy_iso = datetime.date.today().isoformat()
    tarea_a_borrar = None

    if fecha_iso == hoy_iso:
        if 0 <= idx < len(storage.TAREAS_HOY):
            tarea_a_borrar = storage.TAREAS_HOY.pop(idx)
            storage.recalcular_rendimiento()
    else:
        historial = storage.cargar_historial()
        lista = _obtener_lista_dia(fecha_iso, historial)
        if 0 <= idx < len(lista):
            tarea_a_borrar = lista.pop(idx)
            storage.recalcular_dia_historial(fecha_iso, historial)
            storage.guardar_historial(historial)

    if tarea_a_borrar and tarea_a_borrar.get("google_event_id"):
        try: eliminar_evento_calendario(tarea_a_borrar["google_event_id"])
        except Exception: pass
    return jsonify({"status": "ok"})

@calendario_bp.route('/calendario')
def vista_calendario():
    hoy_date = datetime.date.today()
    semana_datos, linea_roja_top, mes_titulo = _construir_semana_datos(referencia_date=hoy_date, sincronizar=True)
    meses = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

    horas_etiquetas = [("12 AM" if h == 0 else f"{h} AM" if h < 12 else "12 PM" if h == 12 else f"{h-12} PM") for h in range(24)]
    todos_eventos = _formatear_eventos_para_vista()

    html = render_template_string(
        CALENDARIO_HTML,
        semana_datos=semana_datos,
        horas_etiquetas=horas_etiquetas,
        linea_roja_top=linea_roja_top,
        mes_actual=meses[hoy_date.month],
        mes_num=hoy_date.month,
        anio_actual=hoy_date.year,
        dia_hoy_num=hoy_date.day,
        hoy_iso=hoy_date.isoformat(),
        primeros_eventos=todos_eventos[:5],
        todos_eventos=todos_eventos,
        hay_mas_eventos=len(todos_eventos) > 5
    )
    return render_layout(html, css_extra="calendario.css")