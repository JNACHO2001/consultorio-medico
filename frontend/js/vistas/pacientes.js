import { api, ErrorApi } from "../api.js";
import {
  alerta, areaTexto, aviso, campo, datosDe, debounce, edad, entrada, fechaHora, h, abrirDialogo, pesos, seleccion, sello, soloFecha,
  TIPOS_INGRESO,
} from "../ui.js";
import { abrirAdmision } from "./admision.js";

const TIPOS = [["CC", "Cédula de ciudadanía"], ["TI", "Tarjeta de identidad"], ["CE", "Cédula de extranjería"], ["PA", "Pasaporte"], ["RC", "Registro civil"]];

export async function montarPacientes(raiz, { usuario }) {
  const esRecepcion = usuario.rol === "RECEPCION";
  const buscador = entrada("q", { tipo: "search", placeholder: "Documento o nombre", "aria-label": "Filtrar pacientes" });
  const lista = h("ul", { class: "resultados" });
  const estadoLista = h("div", { "aria-live": "polite" });
  const detalle = h("div");
  let seleccionado = null;

  async function buscar() {
    const q = buscador.value.trim();
    seleccionado = null;
    detalle.replaceChildren(vacio("Elija un paciente de la lista para ver su información."));
    try {
      // Sin texto se listan todos los pacientes.
      const resultados = await api.get("/api/pacientes", { q });
      estadoLista.replaceChildren(h("p", { class: "suave pequeno" },
        resultados.length
          ? (q ? `${resultados.length} ${resultados.length === 1 ? "resultado" : "resultados"}` : `${resultados.length} ${resultados.length === 1 ? "paciente registrado" : "pacientes registrados"}`)
          : "No hay pacientes con ese dato."));
      lista.replaceChildren(...resultados.map((p) =>
        h("li", {}, h("button", { type: "button", "aria-pressed": "false", onclick: (e) => elegir(p.id, e.currentTarget) },
          h("b", {}, p.nombre_completo),
          h("span", { class: "num" }, `${p.tipo_documento} ${p.numero_documento}`, p.eps ? ` · ${p.eps}` : "")))));
    } catch (error) {
      estadoLista.replaceChildren(alerta(error));
    }
  }

  async function elegir(id, boton) {
    for (const b of lista.querySelectorAll("button")) b.setAttribute("aria-pressed", String(b === boton));
    seleccionado = id;
    await mostrarPaciente(id);
  }

  async function mostrarPaciente(id) {
    detalle.replaceChildren(h("p", { class: "cargando" }, "Cargando paciente…"));
    try {
      const p = await api.get(`/api/pacientes/${id}`);
      if (seleccionado !== id) return;
      detalle.replaceChildren(fichaPaciente(p));
      detalle.append(await panelIngresos(id));
      if (usuario.rol === "MEDICO") detalle.append(await historialClinico(id));
    } catch (error) {
      detalle.replaceChildren(alerta(error));
    }
  }

  function fichaPaciente(p) {
    const dato = (t, v) => h("div", {}, h("dt", {}, t), h("dd", {}, v || "—"));
    return h("section", { class: "panel" },
      h("div", { class: "barra", style: "justify-content:space-between;align-items:start" },
        h("div", {}, h("h2", {}, p.nombre_completo), h("p", { class: "suave num" }, `${p.tipo_documento} ${p.numero_documento}`)),
        esRecepcion
          ? h("div", { class: "acciones", style: "margin:0" },
            h("button", { class: "btn btn-primario", type: "button", onclick: () => abrirAdmision({ paciente: p, alCrear: (i) => { window.location.hash = `#/ingreso/${i.id}`; } }) }, "Ingresar paciente"),
            h("button", { class: "btn", type: "button", onclick: () => formularioPaciente(p) }, "Editar datos"))
          : null),
      p.alergias ? h("div", { class: "alergias" }, h("b", {}, "Alergias: "), p.alergias) : null,
      h("dl", { class: "ficha" },
        dato("Fecha de nacimiento", p.fecha_nacimiento ? `${soloFecha(p.fecha_nacimiento)} (${edad(p.fecha_nacimiento)})` : ""),
        dato("Sexo", p.sexo), dato("Teléfono", p.telefono), dato("Correo", p.correo), dato("EPS", p.eps)),
      esRecepcion && p.historial_cambios.length
        ? h("details", {}, h("summary", {}, `Cambios en los datos (${p.historial_cambios.length})`),
          h("div", { class: "tabla-contenedor" }, h("table", {},
            h("thead", {}, h("tr", {}, ["Fecha", "Campo", "Antes", "Después"].map((t) => h("th", {}, t)))),
            h("tbody", {}, p.historial_cambios.map((c) => h("tr", {},
              h("td", { class: "fecha" }, fechaHora(c.fecha)), h("td", {}, c.campo), h("td", {}, c.valor_anterior || "—"), h("td", {}, c.valor_nuevo || "—")))))))
        : null
    );
  }

  async function panelIngresos(id) {
    const esMedico = usuario.rol === "MEDICO";
    const panel = h("section", { class: "panel" }, h("h3", {}, esMedico ? "Ingresos y procedimientos" : "Ingresos y cuentas"));
    try {
      const ingresos = await api.get(`/api/pacientes/${id}/ingresos`);
      if (!ingresos.length) panel.append(vacio("Este paciente no tiene ingresos."));
      for (const i of ingresos) {
        panel.append(h("article", { class: "consulta-previa" },
          h("h3", {}, fechaHora(i.fecha_ingreso), " · ", TIPOS_INGRESO[i.tipo], " · ", i.medico_nombre, " ", sello(i.estado)),
          h("p", { class: "suave pequeno" }, i.motivo),
          i.procedimientos.length
            ? h("ul", { class: "lista-simple" }, i.procedimientos.map((p) => h("li", {},
              h("span", { class: p.anulado ? "tachada" : "" }, `${p.cantidad} × ${p.nombre}`),
              p.anulado ? " (anulado)" : h("span", { class: "suave num" }, ` · ${pesos(p.subtotal)}`),
              p.observaciones ? h("div", { class: "suave pequeno" }, p.observaciones) : null)))
            : h("p", { class: "suave pequeno" }, "Sin procedimientos registrados."),
          h("p", { class: "pequeno" }, h("b", {}, `Total ${pesos(i.total)}`), i.pendiente_facturar ? ` · por facturar ${pesos(i.pendiente_facturar)}` : "", " · ",
            h("a", { href: `#/ingreso/${i.id}` }, "Abrir cuenta"))));
      }
    } catch (error) {
      panel.append(alerta(error));
    }
    return panel;
  }

  async function historialClinico(id) {
    const panel = h("section", { class: "panel" }, h("h3", {}, "Historia clínica"));
    try {
      const consultas = await api.get(`/api/pacientes/${id}/historial`);
      panel.append(h("p", { class: "suave pequeno" }, "Cada vez que se abre una historia clínica queda registrado en la bitácora."));
      if (!consultas.length) panel.append(vacio("Este paciente aún no tiene consultas registradas."));
      for (const c of consultas) panel.append(consultaPrevia(c));
    } catch (error) {
      panel.append(alerta(error));
    }
    return panel;
  }

  function formularioPaciente(paciente) {
    const nuevo = !paciente;
    abrirDialogo({
      titulo: nuevo ? "Registrar paciente" : "Editar datos del paciente",
      ancho: true,
      construir: (cuerpo, cerrar) => {
        const p = paciente || {};
        const mensaje = h("div");
        const guardar = h("button", { class: "btn btn-primario", type: "submit" }, nuevo ? "Registrar paciente" : "Guardar cambios");
        const form = h("form", {
          onsubmit: async (e) => {
            e.preventDefault();
            mensaje.replaceChildren();
            guardar.disabled = true;
            const datos = datosDe(form);
            try {
              let resultado;
              if (nuevo) resultado = await api.post("/api/pacientes", datos);
              else {
                delete datos.tipo_documento;
                delete datos.numero_documento;
                resultado = await api.put(`/api/pacientes/${p.id}`, datos);
              }
              cerrar();
              aviso(nuevo ? "Paciente registrado." : "Datos actualizados.");
              buscador.value = resultado.numero_documento;
              await buscar();
              const boton = lista.querySelector("button");
              if (boton) await elegir(resultado.id, boton);
            } catch (error) {
              mensaje.replaceChildren(alerta(error));
              if (error instanceof ErrorApi && error.cuerpo.paciente_existente) {
                const existente = error.cuerpo.paciente_existente;
                mensaje.append(h("button", { class: "btn", type: "button", onclick: async () => {
                  cerrar();
                  buscador.value = existente.numero_documento;
                  await buscar();
                  const boton = lista.querySelector("button");
                  if (boton) await elegir(existente.id, boton);
                } }, `Ver a ${existente.nombre_completo}`));
              }
              mensaje.scrollIntoView({ block: "nearest" });
            } finally {
              guardar.disabled = false;
            }
          },
        },
          mensaje,
          h("div", { class: "rejilla-campos" },
            nuevo ? campo("Tipo de documento", seleccion("tipo_documento", TIPOS, "CC")) : null,
            nuevo ? campo("Número de documento", entrada("numero_documento", { requerido: true, inputmode: "numeric" })) : null,
            campo("Nombres", entrada("nombres", { valor: p.nombres, requerido: true })),
            campo("Apellidos", entrada("apellidos", { valor: p.apellidos, requerido: true })),
            campo("Fecha de nacimiento", entrada("fecha_nacimiento", { tipo: "date", valor: p.fecha_nacimiento, requerido: true })),
            campo("Sexo", seleccion("sexo", [["", "Sin indicar"], ["Femenino", "Femenino"], ["Masculino", "Masculino"], ["Otro", "Otro"]], p.sexo || "")),
            campo("Teléfono", entrada("telefono", { tipo: "tel", valor: p.telefono })),
            campo("Correo electrónico", entrada("correo", { tipo: "email", valor: p.correo })),
            campo("EPS", entrada("eps", { valor: p.eps }))),
          campo("Alergias conocidas", areaTexto("alergias", p.alergias, { rows: 2 })),
          nuevo ? null : h("p", { class: "suave pequeno" }, "El tipo y número de documento identifican al paciente y no se pueden cambiar."),
          h("div", { class: "acciones derecha" },
            h("button", { class: "btn", type: "button", onclick: cerrar }, "Cancelar"), guardar));
        cuerpo.append(form);
      },
    });
  }

  buscador.addEventListener("input", debounce(buscar, 300));
  raiz.append(
    h("header", { class: "encabezado" },
      h("div", {}, h("h1", {}, "Pacientes"),
        h("p", {}, esRecepcion ? "Todos los pacientes registrados. Filtre por documento o nombre, registre uno nuevo o ingréselo." : "Todos los pacientes registrados. Elija uno para ver su historia clínica.")),
      esRecepcion ? h("button", { class: "btn btn-primario", type: "button", onclick: () => formularioPaciente(null) }, "Registrar paciente") : null),
    h("div", { class: "dos-columnas" },
      h("section", { class: "panel" }, campo("Filtrar pacientes", buscador), estadoLista, lista),
      detalle)
  );
  await buscar();
}

export function vacio(texto) {
  return h("div", { class: "vacio" }, texto);
}

export function consultaPrevia(c) {
  const fila = (t, v) => (v ? [h("dt", {}, t), h("dd", {}, v)] : []);
  return h("article", { class: "consulta-previa" },
    h("h3", {}, c.fecha_hora ? fechaHora(c.fecha_hora) : "Consulta", " · ", c.medico_nombre || "Médico",
      " ", h("span", { class: "suave pequeno" }, c.cerrada ? "(cerrada)" : "(abierta)")),
    h("dl", {},
      fila("Motivo", c.motivo), fila("Antecedentes", c.antecedentes), fila("Signos vitales", c.signos_vitales),
      fila("Diagnóstico", c.diagnostico), fila("Tratamiento", c.tratamiento), fila("Fórmula", c.formula), fila("Observaciones", c.observaciones)),
    ...(c.notas || []).map((n) => h("div", { class: "nota" }, h("small", {}, `Nota aclaratoria · ${fechaHora(n.fecha)}`), n.texto)));
}
