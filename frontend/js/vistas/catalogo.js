import { api } from "../api.js";
import { abrirDialogo, alerta, aviso, campo, confirmar, datosDe, entrada, h, pesos } from "../ui.js";
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
          h("thead", {}, h("tr", {}, ["Código", "Procedimiento", "Tarifa", edita ? "" : null].filter((t) => t !== null).map((t, i) => h("th", { class: i === 2 ? "num" : "" }, t)))),
          h("tbody", {}, lista.map((p) => h("tr", {},
            h("td", { class: "num-izq" }, p.codigo), h("td", {}, h("b", {}, p.nombre)), h("td", { class: "num" }, pesos(p.tarifa)),
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
              else await api.put(`/api/procedimientos/${p.id}`, { nombre: datos.nombre, tarifa: datos.tarifa });
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
          h("div", { class: "acciones derecha" }, h("button", { class: "btn", type: "button", onclick: cerrar }, "Cancelar"), guardar));
        cuerpo.append(form);
      },
    });
  }

  raiz.append(
    h("header", { class: "encabezado" },
      h("div", {}, h("h1", {}, "Catálogo de procedimientos"),
        h("p", {}, edita ? "Procedimientos que el consultorio presta y su tarifa vigente." : "Procedimientos disponibles y su tarifa vigente.")),
      edita ? h("button", { class: "btn btn-primario", type: "button", onclick: () => formulario(null) }, "Agregar procedimiento") : null),
    h("section", { class: "panel" }, zona));
  await cargar();
}
