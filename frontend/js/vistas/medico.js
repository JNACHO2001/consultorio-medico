import { api, ErrorApi } from "../api.js";
import {
  alerta, anexar, areaTexto, aviso, campo, confirmar, datosDe, edad, entrada, fechaHora, fechaLarga, h, hoyISO, horaCorta, sello, sumarDias,
} from "../ui.js";
import { consultaPrevia, vacio } from "./pacientes.js";

// Citas que el médico vio en su agenda: la pantalla de atención las necesita para abrirse.
const citasVistas = new Map();

export async function montarMiAgenda(raiz, { usuario }) {
  const estado = { fecha: hoyISO() };
  const zona = h("div", { "aria-live": "polite" });
  const selFecha = entrada("fecha", { tipo: "date", valor: estado.fecha, onchange: (e) => { if (e.target.value) { estado.fecha = e.target.value; cargar(); } } });
  const mover = (n) => { estado.fecha = sumarDias(estado.fecha, n); selFecha.value = estado.fecha; cargar(); };

  async function cargar() {
    zona.replaceChildren(h("p", { class: "cargando" }, "Cargando agenda…"));
    try {
      const citas = (await api.get("/api/citas/agenda", { medico_id: usuario.id, fecha: estado.fecha }))
        .filter((c) => c.estado !== "CANCELADA");
      citas.forEach((c) => citasVistas.set(c.id, c));
      const pendientes = citas.filter((c) => c.estado === "PROGRAMADA").length;
      zona.replaceChildren(
        h("h2", { class: "titulo-dia" }, fechaLarga(estado.fecha)),
        h("p", { class: "resumen-dia" }, `${citas.length} ${citas.length === 1 ? "cita" : "citas"} · ${pendientes} por atender`),
        citas.length
          ? h("ol", { class: "linea-tiempo" }, citas.map((c) => h("li", { class: `franja ocupada ${c.estado === "ATENDIDA" ? "atendida" : ""}` },
            h("div", { class: "hora" }, horaCorta(c.fecha_hora)),
            h("div", { class: "contenido" },
              h("div", { class: `cita ${c.estado === "ATENDIDA" ? "atendida" : ""}`, style: "cursor:default" },
                h("span", { class: "quien" }, h("b", {}, c.paciente_nombre), h("span", { class: "num" }, c.paciente_documento)),
                h("span", { style: "display:flex;gap:.6rem;align-items:center" }, sello(c.estado),
                  h("a", { class: "btn btn-pequeno " + (c.estado === "PROGRAMADA" ? "btn-primario" : ""), href: `#/atencion/${c.id}` },
                    c.estado === "PROGRAMADA" ? "Atender" : "Ver consulta")))))))
          : vacio("No tiene citas este día."));
    } catch (error) {
      zona.replaceChildren(alerta(error));
    }
  }

  raiz.append(
    h("header", { class: "encabezado" }, h("div", {}, h("h1", {}, "Mi agenda"), h("p", {}, `${usuario.nombre_completo}${usuario.especialidad ? " · " + usuario.especialidad : ""}`))),
    h("div", { class: "panel" },
      h("div", { class: "barra" },
        h("div", { class: "dia-nav" },
          h("button", { class: "btn", type: "button", "aria-label": "Día anterior", onclick: () => mover(-1) }, "‹"),
          campo("Fecha", selFecha),
          h("button", { class: "btn", type: "button", "aria-label": "Día siguiente", onclick: () => mover(1) }, "›"),
          h("button", { class: "btn", type: "button", onclick: () => { estado.fecha = hoyISO(); selFecha.value = estado.fecha; cargar(); } }, "Hoy"))),
      zona));
  await cargar();
}

const CAMPOS = [
  ["motivo", "Motivo de consulta", 2, true],
  ["antecedentes", "Antecedentes", 2],
  ["signos_vitales", "Signos vitales", 2],
  ["diagnostico", "Diagnóstico", 3],
  ["tratamiento", "Tratamiento", 3],
  ["formula", "Fórmula médica", 3],
  ["observaciones", "Observaciones", 2],
];

export async function montarAtencion(raiz, { usuario, parametros }) {
  const citaId = Number(parametros[0]);
  let cita = citasVistas.get(citaId);
  if (!cita) {
    // Entrada directa por enlace: se busca la cita en la agenda de hoy y de los próximos días.
    const hoy = hoyISO();
    const lista = await api.get("/api/citas/agenda", { medico_id: usuario.id, fecha: sumarDias(hoy, -3), dias: 7 });
    lista.forEach((c) => citasVistas.set(c.id, c));
    cita = citasVistas.get(citaId);
  }
  if (!cita) {
    raiz.append(alerta("No se encontró la cita. Ábrala desde su agenda."), h("a", { class: "btn", href: "#/mi-agenda" }, "Ir a mi agenda"));
    return;
  }

  const [paciente, historial] = await Promise.all([api.get(`/api/pacientes/${cita.paciente_id}`), api.get(`/api/pacientes/${cita.paciente_id}/historial`)]);
  let consulta = null;
  try {
    consulta = await api.get(`/api/consultas/por-cita/${citaId}`);
  } catch (error) {
    if (!(error instanceof ErrorApi && error.estado === 404)) throw error;
  }

  const mensaje = h("div", { "aria-live": "polite" });
  const zonaEstado = h("span", {}, sello(cita.estado));
  const zonaConsulta = h("section", { class: "panel" });
  const zonaNotas = h("div");

  function pintarFormulario() {
    const cerrada = consulta?.cerrada === true;
    const controles = CAMPOS.filter(([nombre]) => !cerrada || nombre === "motivo" || consulta?.[nombre]).map(([nombre, etiqueta, filas, req]) =>
      campo(etiqueta, areaTexto(nombre, consulta?.[nombre] ?? "", { rows: filas, readonly: cerrada, required: req && !cerrada })));
    const form = h("form", { novalidate: false });
    const guardar = h("button", { class: "btn", type: "submit" }, consulta ? "Guardar cambios" : "Guardar borrador");
    const cerrarBtn = h("button", { class: "btn btn-primario", type: "button" }, "Cerrar consulta");

    async function guardarDatos() {
      const datos = datosDe(form);
      consulta = consulta
        ? await api.put(`/api/consultas/${consulta.id}`, datos)
        : await api.post("/api/consultas", { cita_id: citaId, ...datos });
    }

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      mensaje.replaceChildren();
      guardar.disabled = true;
      try {
        await guardarDatos();
        aviso("Consulta guardada.");
        pintarFormulario();
      } catch (error) {
        mensaje.replaceChildren(alerta(error));
        mensaje.scrollIntoView({ block: "nearest" });
        guardar.disabled = false;
      }
    });

    cerrarBtn.addEventListener("click", async () => {
      mensaje.replaceChildren();
      if (!form.reportValidity()) return;
      const ok = await confirmar({
        titulo: "Cerrar la consulta",
        mensaje: "Al cerrarla ya no podrá editarla; solo podrá agregar notas aclaratorias. ¿Desea continuar?",
        textoConfirmar: "Cerrar consulta",
      });
      if (!ok) return;
      cerrarBtn.disabled = true;
      try {
        await guardarDatos();
        consulta = await api.post(`/api/consultas/${consulta.id}/cerrar`);
        cita.estado = "ATENDIDA";
        zonaEstado.replaceChildren(sello(cita.estado));
        aviso("Consulta cerrada. La cita quedó como atendida.");
        pintarFormulario();
      } catch (error) {
        mensaje.replaceChildren(alerta(error));
        mensaje.scrollIntoView({ block: "nearest" });
        cerrarBtn.disabled = false;
      }
    });

    form.append(...controles);
    if (!cerrada) form.append(h("div", { class: "acciones" }, guardar, cerrarBtn));
    zonaConsulta.replaceChildren();
    anexar(zonaConsulta, [
      h("h2", {}, cerrada ? "Consulta cerrada" : consulta ? "Consulta en curso" : "Nueva consulta"),
      cerrada ? h("div", { class: "alerta info cerrada-aviso" }, "Esta consulta está cerrada y no se puede modificar. Para corregir algo, agregue una nota aclaratoria.") : null,
      form]);
    pintarNotas();
  }

  function pintarNotas() {
    if (!consulta?.cerrada) return zonaNotas.replaceChildren();
    const texto = areaTexto("texto", "", { rows: 3, required: true, placeholder: "Escriba la aclaración o corrección" });
    const aviso_ = h("div");
    const boton = h("button", { class: "btn btn-primario", type: "submit" }, "Agregar nota aclaratoria");
    zonaNotas.replaceChildren(h("section", { class: "panel" },
      h("h2", {}, "Notas aclaratorias"),
      ...(consulta.notas.length ? consulta.notas.map((n) => h("div", { class: "nota" }, h("small", {}, fechaHora(n.fecha)), n.texto)) : [h("p", { class: "suave" }, "Todavía no hay notas.")]),
      h("form", {
        onsubmit: async (e) => {
          e.preventDefault();
          boton.disabled = true;
          try {
            consulta = await api.post(`/api/consultas/${consulta.id}/notas`, { texto: texto.value.trim() });
            aviso("Nota agregada.");
            pintarNotas();
          } catch (error) {
            aviso_.replaceChildren(alerta(error));
            boton.disabled = false;
          }
        },
      }, aviso_, campo("Nueva nota", texto), h("div", { class: "acciones" }, boton))));
  }

  const previas = historial.filter((c) => c.id !== consulta?.id);
  anexar(raiz, [
    h("a", { class: "btn btn-enlace", href: "#/mi-agenda" }, "‹ Volver a mi agenda"),
    h("header", { class: "encabezado", style: "margin-top:.6rem" },
      h("div", {}, h("h1", {}, paciente.nombre_completo),
        h("p", { class: "num" }, `${paciente.tipo_documento} ${paciente.numero_documento}`, paciente.fecha_nacimiento ? ` · ${edad(paciente.fecha_nacimiento)}` : "", paciente.eps ? ` · ${paciente.eps}` : "")),
      h("div", {}, h("span", { class: "num" }, `${fechaLarga(cita.fecha_hora.slice(0, 10))}, ${horaCorta(cita.fecha_hora)}  `), zonaEstado)),
    paciente.alergias ? h("div", { class: "alergias" }, h("b", {}, "Alergias: "), paciente.alergias) : null,
    h("div", { class: "atencion" },
      h("div", {}, mensaje, zonaConsulta, zonaNotas),
      h("aside", { class: "panel" },
        h("h2", {}, "Historia clínica"),
        previas.length ? previas.map(consultaPrevia) : vacio("Primera consulta de este paciente.")))]);
  pintarFormulario();
}
