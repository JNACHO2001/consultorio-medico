import { api } from "../api.js";
import { alerta, aviso, fechaHora, h } from "../ui.js";

const ESTADOS = { PROGRAMADO: "Programado", ENVIADO: "Enviado", CANCELADO: "Cancelado" };
const CLASE = { PROGRAMADO: "programada", ENVIADO: "atendida", CANCELADO: "cancelada" };

export async function montarRecordatorios(raiz, { usuario }) {
  const zona = h("div");

  async function cargar() {
    try {
      const filas = await api.get("/api/recordatorios");
      zona.replaceChildren(filas.length
        ? h("div", { class: "tabla-contenedor" }, h("table", {},
          h("thead", {}, h("tr", {}, ["Se envía", "Destinatario", "Medio", "Cita", "Estado"].map((t) => h("th", {}, t)))),
          h("tbody", {}, filas.map((r) => h("tr", {},
            h("td", { class: "fecha" }, fechaHora(r.fecha_envio)), h("td", {}, r.destinatario || "Sin correo registrado"),
            h("td", {}, r.canal === "CORREO" ? "Correo" : r.canal), h("td", { class: "fecha" }, `#${r.cita_id}`),
            h("td", {}, h("span", { class: `sello ${CLASE[r.estado]}` }, ESTADOS[r.estado] || r.estado)))))))
        : h("div", { class: "vacio" }, "Todavía no hay recordatorios. Se crean al agendar una cita."));
    } catch (error) {
      zona.replaceChildren(alerta(error));
    }
  }

  const procesar = h("button", {
    class: "btn btn-primario", type: "button",
    onclick: async () => {
      procesar.disabled = true;
      try {
        const enviados = await api.post("/api/recordatorios/procesar");
        aviso(enviados.length ? `${enviados.length} recordatorio(s) enviado(s).` : "No había recordatorios por enviar.");
        await cargar();
      } catch (error) {
        aviso(error.message, "error");
      } finally {
        procesar.disabled = false;
      }
    },
  }, "Enviar los que ya vencieron");

  raiz.append(
    h("header", { class: "encabezado" },
      h("div", {}, h("h1", {}, "Recordatorios de citas"),
        h("p", {}, "Se programan 24 horas antes de cada cita. En este prototipo el envío es simulado: no sale ningún correo real.")),
      usuario.rol === "ADMINISTRADOR" ? procesar : null),
    h("section", { class: "panel" }, zona));
  await cargar();
}
