import { api } from "../api.js";
import { alerta, campo, h, seleccion, AREAS_APOYO } from "../ui.js";
import { abrirResultado, formResultado, tablaOrdenes } from "./ordenes.js";

// Cola de apoyo diagnóstico: órdenes por realizar y resultados registrados.
export async function montarLaboratorio(raiz) {
  const estado = seleccion("estado", [["SOLICITADA", "Por realizar"], ["REALIZADA", "Con resultado"], ["", "Todas"]], "SOLICITADA");
  const area = seleccion("area", [["", "Todas las áreas"], ...Object.entries(AREAS_APOYO).filter(([v]) => v !== "NINGUNA")], "");
  const zona = h("div", { "aria-live": "polite" });

  async function cargar() {
    zona.replaceChildren(h("p", { class: "cargando" }, "Cargando órdenes…"));
    try {
      const ordenes = await api.get("/api/ordenes", { estado: estado.value, area: area.value });
      ordenes.sort((a, b) => (a.prioridad === b.prioridad ? 0 : a.prioridad === "URGENTE" ? -1 : 1));
      zona.replaceChildren(tablaOrdenes(ordenes, {
        mostrarPaciente: true,
        acciones: (o) => o.estado === "SOLICITADA"
          ? [h("button", { class: "btn btn-pequeno btn-primario", type: "button", onclick: () => formResultado(o, cargar) }, "Registrar resultado")]
          : o.estado === "REALIZADA" ? [h("button", { class: "btn btn-pequeno", type: "button", onclick: () => abrirResultado(o) }, "Ver resultado")] : [],
      }));
    } catch (error) {
      zona.replaceChildren(alerta(error));
    }
  }

  estado.addEventListener("change", cargar);
  area.addEventListener("change", cargar);
  raiz.append(
    h("header", { class: "encabezado" },
      h("div", {}, h("h1", {}, "Apoyo diagnóstico"),
        h("p", {}, "Órdenes de los médicos por realizar. Al registrar el resultado, el servicio se cobra en la cuenta del paciente."))),
    h("section", { class: "panel" }, h("div", { class: "barra" }, campo("Estado", estado), campo("Área", area)), zona));
  await cargar();
}
