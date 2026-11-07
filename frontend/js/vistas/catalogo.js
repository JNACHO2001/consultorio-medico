import { api } from "../api.js";
import { abrirDialogo, alerta, aviso, campo, confirmar, datosDe, entrada, h, pesos, AREAS_APOYO, seleccion, TIPOS_SERVICIO } from "../ui.js";
import { vacio } from "./pacientes.js";

// Catálogo de procedimientos y tarifas. Todos los roles lo consultan; solo el administrador lo cambia.
export async function montarCatalogo(raiz, { usuario }) {
  const edita = usuario.rol === "ADMINISTRADOR";
  const zona = h("div", { "aria-live": "polite" });

  async function cargar() {
    try {
      const lista = await api.get("/api/procedimientos");
      zona.replaceChildren(lista.length
        ? h("div", { class: "tabla-contenedor" }, h("table", {},
          h("thead", {}, h("tr", {}, ["Código", "Procedimiento", "CUPS", "Tarifa base", edita ? "" : null].filter((t) => t !== null).map((t, i) => h("th", { class: i === 3 ? "num" : "" }, t)))),
          h("tbody", {}, lista.map((p) => h("tr", {},
            h("td", { class: "num-izq" }, p.codigo), h("td", {}, h("b", {}, p.nombre), h("div", { class: "suave pequeno" }, TIPOS_SERVICIO[p.tipo_servicio] || "", p.area_apoyo !== "NINGUNA" ? ` · ${AREAS_APOYO[p.area_apoyo]}` : "")),
            h("td", { class: "num-izq" }, p.cups || h("span", { class: "suave" }, "Sin CUPS")), h("td", { class: "num" }, pesos(p.tarifa)),
            edita ? h("td", {}, h("div", { class: "celda-acciones" },
              h("button", { class: "btn btn-pequeno", type: "button", onclick: () => formulario(p) }, "Editar"),
              h("button", { class: "btn btn-pequeno btn-peligro", type: "button", onclick: () => retirar(p) }, "Retirar"))) : null)))))
        : vacio("El catálogo está vacío."));
    } catch (error) {
      zona.replaceChildren(alerta(error));
    }
  }

  async function retirar(p) {
    const ok = await confirmar({
      titulo: "Retirar del catálogo",
      mensaje: `${p.nombre} dejará de ofrecerse para nuevos procedimientos. Lo ya realizado y facturado no cambia.`,
      textoConfirmar: "Retirar", peligro: true,
    });
    if (!ok) return;
    try {
      await api.post(`/api/procedimientos/${p.id}/desactivar`);
      aviso("Procedimiento retirado.");
      cargar();
    } catch (error) {
      aviso(error.message, "error");
    }
  }

  function formulario(p) {
    const nuevo = !p;
    abrirDialogo({
      titulo: nuevo ? "Agregar procedimiento" : `Editar ${p.codigo}`,
      construir: (cuerpo, cerrar) => {
        const mensaje = h("div");
        const guardar = h("button", { class: "btn btn-primario", type: "submit" }, "Guardar");
        const form = h("form", {
          onsubmit: async (e) => {
            e.preventDefault();
            guardar.disabled = true;
            const datos = datosDe(form);
            datos.tarifa = Number(datos.tarifa);
            try {
              if (nuevo) await api.post("/api/procedimientos", datos);
              else await api.put(`/api/procedimientos/${p.id}`, { nombre: datos.nombre, tarifa: datos.tarifa, cups: datos.cups, tipo_servicio: datos.tipo_servicio, area_apoyo: datos.area_apoyo });
              cerrar();
              aviso(nuevo ? "Procedimiento agregado." : "Cambios guardados.");
              cargar();
            } catch (error) {
              mensaje.replaceChildren(alerta(error));
              guardar.disabled = false;
            }
          },
        }, mensaje,
          nuevo ? campo("Código", entrada("codigo", { requerido: true, maxlength: 12 }), "Letras, números o guiones. Ej.: ECO-001") : null,
          campo("Nombre del procedimiento", entrada("nombre", { valor: p?.nombre, requerido: true, maxlength: 120 })),
          campo("Tarifa (pesos)", entrada("tarifa", { tipo: "number", valor: p?.tarifa, requerido: true, min: 1, step: 1, inputmode: "numeric" }),
            nuevo ? null : "El cambio solo aplica a procedimientos nuevos; lo ya realizado conserva su valor."),
          h("div", { class: "rejilla-campos" },
            campo("Código CUPS", entrada("cups", { valor: p?.cups, maxlength: 6, pattern: "[0-9]{6}|", inputmode: "numeric" }), "6 dígitos. Lo exige el RIPS; puede dejarlo vacío por ahora."),
            campo("Tipo de servicio", seleccion("tipo_servicio", Object.entries(TIPOS_SERVICIO), p?.tipo_servicio || "PROCEDIMIENTO"), "Define en qué grupo del RIPS se reporta."),
            campo("Apoyo diagnóstico", seleccion("area_apoyo", Object.entries(AREAS_APOYO), p?.area_apoyo || "NINGUNA"), "Si no es «No es de apoyo», el médico lo puede ordenar y lo realiza apoyo diagnóstico.")),
          h("div", { class: "acciones derecha" }, h("button", { class: "btn", type: "button", onclick: cerrar }, "Cancelar"), guardar));
        cuerpo.append(form);
      },
    });
  }

  raiz.append(
    h("header", { class: "encabezado" },
      h("div", {}, h("h1", {}, "Catálogo de procedimientos"),
        h("p", {}, edita ? "Procedimientos que la IPS presta, su código CUPS y su tarifa base. Cada convenio la ajusta con su porcentaje pactado." : "Procedimientos disponibles y su tarifa vigente.")),
      edita ? h("button", { class: "btn btn-primario", type: "button", onclick: () => formulario(null) }, "Agregar procedimiento") : null),
    h("section", { class: "panel" }, zona));
  await cargar();
}
