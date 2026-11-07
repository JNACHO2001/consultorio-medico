import { api } from "../api.js";
import {
  abrirDialogo, alerta, anexar, areaTexto, aviso, campo, datosDe, entrada, fechaHora, h, METODOS_PAGO, pesos, sello,
} from "../ui.js";
import { vacio } from "./pacientes.js";

const nombreMetodo = (m) => METODOS_PAGO.find(([v]) => v === m)?.[1] || m;

function tablaRecibos(recibos) {
  return recibos.length
    ? h("div", { class: "tabla-contenedor" }, h("table", {},
      h("thead", {}, h("tr", {}, ["Recibo", "Hora", "Factura", "Paciente", "Pagó", "Forma", "Valor"].map((t, i) => h("th", { class: i === 6 ? "num" : "" }, t)))),
      h("tbody", {}, recibos.map((r) => h("tr", {},
        h("td", { class: "num-izq" }, h("b", {}, r.recibo_numero)), h("td", { class: "fecha" }, fechaHora(r.fecha)),
        h("td", { class: "num-izq" }, r.factura_numero), h("td", {}, r.paciente_nombre),
        h("td", {}, r.origen === "PAGADOR" ? "Pagador" : "Paciente"), h("td", {}, nombreMetodo(r.metodo)),
        h("td", { class: "num" }, pesos(r.valor)))))))
    : vacio("Todavía no hay recibos en este turno.");
}

function cifra(titulo, valor, tono = "") {
  return h("div", { class: `cifra ${tono}` }, h("small", {}, titulo), h("b", { class: "num" }, valor));
}

function detalleTurno(caja) {
  abrirDialogo({
    titulo: `Turno de caja #${caja.id}`,
    ancho: true,
    construir: (cuerpo) => {
      const dato = (t, v) => h("div", {}, h("dt", {}, t), h("dd", {}, v ?? "—"));
      anexar(cuerpo, [
        h("dl", { class: "ficha" },
          dato("Cajero", caja.cajero_nombre), dato("Apertura", fechaHora(caja.fecha_apertura)),
          dato("Cierre", caja.fecha_cierre ? fechaHora(caja.fecha_cierre) : "Abierta"), dato("Base inicial", pesos(caja.base_inicial)),
          dato("Efectivo esperado", caja.efectivo_esperado != null ? pesos(caja.efectivo_esperado) : pesos(caja.efectivo_esperado_actual)),
          dato("Efectivo contado", caja.efectivo_contado != null ? pesos(caja.efectivo_contado) : "—"),
          dato("Diferencia", caja.diferencia != null ? pesos(caja.diferencia) : "—"), dato("Observaciones", caja.observaciones)),
        h("h3", {}, "Recibos del turno"), tablaRecibos(caja.recibos)]);
    },
  });
}

// Apertura y cierre de caja. El cajero (recepción) gestiona su turno; el administrador consulta todos.
export async function montarCaja(raiz, { usuario }) {
  const esCajero = usuario.rol === "RECEPCION";
  const zona = h("div", { "aria-live": "polite" });

  async function cargar() {
    try {
      const [actual, turnos] = await Promise.all([esCajero ? api.get("/api/caja/actual") : null, api.get("/api/caja")]);
      const historial = turnos.filter((t) => t.estado === "CERRADA");
      zona.replaceChildren(...[
        esCajero ? (actual ? turnoAbierto(actual) : formApertura()) : null,
        h("section", { class: "subseccion" }, h("h2", {}, esCajero ? "Mis turnos cerrados" : "Turnos de caja"),
          (esCajero ? historial : turnos).length ? tablaTurnos(esCajero ? historial : turnos) : vacio("Todavía no hay turnos cerrados."))].filter(Boolean));
    } catch (error) {
      zona.replaceChildren(alerta(error));
    }
  }

  function formApertura() {
    const mensaje = h("div");
    const boton = h("button", { class: "btn btn-primario", type: "submit" }, "Abrir caja");
    const form = h("form", {
      class: "panel",
      onsubmit: async (e) => {
        e.preventDefault();
        boton.disabled = true;
        try {
          await api.post("/api/caja/apertura", { base_inicial: Number(form.elements.base_inicial.value) });
          aviso("Caja abierta. Ya puede cobrar.");
          await cargar();
        } catch (error) {
          mensaje.replaceChildren(alerta(error));
          boton.disabled = false;
        }
      },
    }, h("h2", {}, "No tiene una caja abierta"),
    h("p", { class: "suave" }, "Para cobrar al paciente necesita un turno de caja abierto. Indique el efectivo con que empieza."),
    mensaje,
    h("div", { class: "pago" },
      campo("Base inicial en efectivo (pesos)", entrada("base_inicial", { tipo: "number", valor: 0, min: 0, max: 100000000, step: 1, inputmode: "numeric", requerido: true })),
      boton));
    return form;
  }

  function turnoAbierto(caja) {
    const metodos = Object.entries(caja.por_metodo);
    return h("section", { class: "panel" },
      h("h2", {}, "Mi caja abierta", " ", sello("ABIERTA")),
      h("p", { class: "suave" }, `Abierta el ${fechaHora(caja.fecha_apertura)} con una base de ${pesos(caja.base_inicial)}.`),
      h("div", { class: "resumen-cifras" },
        cifra("Recibos", String(caja.n_recibos)), cifra("Total recibido", pesos(caja.total_recibido), "ok"),
        cifra("Efectivo esperado", pesos(caja.efectivo_esperado_actual), "pendiente"),
        ...metodos.map(([m, v]) => cifra(nombreMetodo(m), pesos(v)))),
      h("h3", {}, "Recibos del turno"), tablaRecibos(caja.recibos),
      h("div", { class: "acciones" }, h("button", { class: "btn btn-primario", type: "button", onclick: () => formCierre(caja) }, "Cerrar caja")));
  }

  function formCierre(caja) {
    abrirDialogo({
      titulo: "Cerrar caja",
      construir: (cuerpo, cerrar) => {
        const mensaje = h("div");
        const boton = h("button", { class: "btn btn-primario", type: "submit" }, "Cerrar turno");
        const dif = h("p", { class: "suave", "aria-live": "polite" });
        const contado = entrada("efectivo_contado", { tipo: "number", requerido: true, min: 0, step: 1, inputmode: "numeric", valor: caja.efectivo_esperado_actual });
        const actualizar = () => {
          const d = Number(contado.value) - caja.efectivo_esperado_actual;
          dif.textContent = Number.isNaN(d) ? "" : d === 0 ? "El efectivo cuadra." : `Diferencia: ${pesos(d)} (${d > 0 ? "sobrante" : "faltante"}). Explíquela en las observaciones.`;
        };
        contado.addEventListener("input", actualizar);
        const form = h("form", {
          onsubmit: async (e) => {
            e.preventDefault();
            boton.disabled = true;
            const d = datosDe(form);
            try {
              const cerrada = await api.post(`/api/caja/${caja.id}/cierre`, { efectivo_contado: Number(d.efectivo_contado), observaciones: d.observaciones });
              cerrar();
              aviso(cerrada.diferencia === 0 ? "Caja cerrada sin diferencias." : "Caja cerrada con diferencia registrada.");
              await cargar();
            } catch (error) {
              mensaje.replaceChildren(alerta(error));
              boton.disabled = false;
            }
          },
        }, mensaje,
        h("p", {}, `El sistema espera ${pesos(caja.efectivo_esperado_actual)} en efectivo (base ${pesos(caja.base_inicial)} más los cobros en efectivo).`),
        campo("Efectivo contado (pesos)", contado), dif,
        campo("Observaciones", areaTexto("observaciones", "", { rows: 2, maxlength: 300 }), "Obligatorias si hay diferencia."),
        h("div", { class: "acciones derecha" }, h("button", { class: "btn", type: "button", onclick: cerrar }, "Volver"), boton));
        cuerpo.append(form);
        actualizar();
      },
    });
  }

  function tablaTurnos(lista) {
    return h("div", { class: "tabla-contenedor" }, h("table", {},
      h("thead", {}, h("tr", {}, ["Turno", "Cajero", "Apertura", "Cierre", "Recibos", "Total", "Diferencia", "Estado", ""].map((t, i) => h("th", { class: i >= 4 && i <= 6 ? "num" : "" }, t)))),
      h("tbody", {}, lista.map((t) => h("tr", {},
        h("td", { class: "num-izq" }, `#${t.id}`), h("td", {}, t.cajero_nombre), h("td", { class: "fecha" }, fechaHora(t.fecha_apertura)),
        h("td", { class: "fecha" }, t.fecha_cierre ? fechaHora(t.fecha_cierre) : "—"), h("td", { class: "num" }, t.n_recibos),
        h("td", { class: "num" }, pesos(t.total_recibido)),
        h("td", { class: `num ${t.diferencia ? "diferencia" : ""}` }, t.diferencia != null ? pesos(t.diferencia) : "—"), h("td", {}, sello(t.estado)),
        h("td", {}, h("button", { class: "btn btn-pequeno", type: "button", onclick: async () => {
          try { detalleTurno(await api.get(`/api/caja/${t.id}`)); } catch (error) { aviso(error.message, "error"); }
        } }, "Ver")))))));
  }

  raiz.append(
    h("header", { class: "encabezado" },
      h("div", {}, h("h1", {}, "Caja"),
        h("p", {}, esCajero ? "Abra su turno para cobrar, vea sus recibos y ciérrelo contando el efectivo." : "Consulta de los turnos de caja y sus diferencias."))),
    zona);
  await cargar();
}
