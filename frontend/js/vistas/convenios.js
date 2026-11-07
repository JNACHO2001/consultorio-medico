import { api } from "../api.js";
import {
  abrirDialogo, alerta, anexar, aviso, campo, confirmar, datosDe, entrada, h, pesos, seleccion, TIPOS_PAGADOR,
} from "../ui.js";
import { vacio } from "./pacientes.js";

// Pagadores (EPS, ARL, SOAT…) y los convenios con su condición de pago. Solo el administrador los cambia.
export async function montarConvenios(raiz) {
  const zona = h("div", { "aria-live": "polite" });

  async function cargar() {
    zona.replaceChildren(h("p", { class: "cargando" }, "Cargando pagadores…"));
    try {
      const pagadores = await api.get("/api/pagadores");
      zona.replaceChildren(...(pagadores.length ? pagadores.map(tarjeta) : [vacio("Todavía no hay pagadores.")]));
    } catch (error) {
      zona.replaceChildren(alerta(error));
    }
  }

  function tarjeta(p) {
    const fijo = p.codigo === "PARTICULAR";
    return h("section", { class: "panel pagador" },
      h("div", { class: "pagador-cabecera" },
        h("div", {},
          h("h2", {}, p.nombre, " ", h("span", { class: "etiqueta" }, TIPOS_PAGADOR[p.tipo] || p.tipo)),
          h("p", { class: "suave pequeno num" }, `Código ${p.codigo}${p.nit ? " · NIT " + p.nit : ""}`)),
        fijo ? h("span", { class: "suave pequeno" }, "Pagador predeterminado: no se edita")
          : h("div", { class: "celda-acciones" },
            h("button", { class: "btn btn-pequeno", type: "button", onclick: () => formPagador(p) }, "Editar"),
            h("button", { class: "btn btn-pequeno", type: "button", onclick: () => formConvenio(p, null) }, "Agregar convenio"),
            h("button", { class: "btn btn-pequeno btn-peligro", type: "button", onclick: () => retirarPagador(p) }, "Retirar"))),
      p.convenios.length
        ? h("div", { class: "tabla-contenedor" }, h("table", {},
          h("thead", {}, h("tr", {}, ["Convenio", "Tarifa", "Copago", "Cuota moderadora", "Autorización", ""].map((t, i) => h("th", { class: i >= 1 && i <= 3 ? "num" : "" }, t)))),
          h("tbody", {}, p.convenios.map((c) => h("tr", {},
            h("td", {}, h("b", {}, c.nombre), c.activo ? null : h("span", { class: "etiqueta" }, "Retirado")),
            h("td", { class: "num" }, `${c.porcentaje_tarifa}%`), h("td", { class: "num" }, `${c.copago_porcentaje}%`),
            h("td", { class: "num" }, pesos(c.cuota_moderadora)), h("td", {}, c.requiere_autorizacion ? "Obligatoria" : "No exige"),
            h("td", {}, fijo || !c.activo ? null : h("div", { class: "celda-acciones" },
              h("button", { class: "btn btn-pequeno", type: "button", onclick: () => formConvenio(p, c) }, "Editar"),
              h("button", { class: "btn btn-pequeno btn-peligro", type: "button", onclick: () => retirarConvenio(c) }, "Retirar"))))))))
        : vacio("Sin convenios. Agregue uno para poder admitir pacientes con este pagador."));
  }

  async function retirarPagador(p) {
    const ok = await confirmar({
      titulo: "Retirar pagador", peligro: true, textoConfirmar: "Retirar",
      mensaje: `${p.nombre} y sus convenios dejarán de ofrecerse en nuevas admisiones. Las facturas ya emitidas se conservan.`,
    });
    if (!ok) return;
    try {
      await api.post(`/api/pagadores/${p.id}/desactivar`);
      aviso("Pagador retirado.");
      cargar();
    } catch (error) {
      aviso(error.message, "error");
    }
  }

  async function retirarConvenio(c) {
    const ok = await confirmar({
      titulo: "Retirar convenio", peligro: true, textoConfirmar: "Retirar",
      mensaje: `${c.nombre} dejará de ofrecerse en nuevas admisiones. Los ingresos y facturas existentes no cambian.`,
    });
    if (!ok) return;
    try {
      await api.post(`/api/convenios/${c.id}/desactivar`);
      aviso("Convenio retirado.");
      cargar();
    } catch (error) {
      aviso(error.message, "error");
    }
  }

  function formPagador(p) {
    const nuevo = !p;
    abrirDialogo({
      titulo: nuevo ? "Agregar pagador" : `Editar ${p.nombre}`,
      construir: (cuerpo, cerrar) => {
        const mensaje = h("div");
        const guardar = h("button", { class: "btn btn-primario", type: "submit" }, "Guardar");
        const tipos = Object.entries(TIPOS_PAGADOR).filter(([v]) => v !== "PARTICULAR");
        const form = h("form", {
          onsubmit: async (e) => {
            e.preventDefault();
            guardar.disabled = true;
            const datos = datosDe(form);
            try {
              if (nuevo) await api.post("/api/pagadores", datos);
              else await api.put(`/api/pagadores/${p.id}`, { nombre: datos.nombre, nit: datos.nit });
              cerrar();
              aviso(nuevo ? "Pagador agregado." : "Cambios guardados.");
              cargar();
            } catch (error) {
              mensaje.replaceChildren(alerta(error));
              guardar.disabled = false;
            }
          },
        }, mensaje,
          nuevo ? h("div", { class: "rejilla-campos" },
            campo("Código", entrada("codigo", { requerido: true, maxlength: 12 }), "Letras, números o guiones. Ej.: EPS-SALUDVIDA"),
            campo("Tipo de pagador", seleccion("tipo", tipos, "EPS"))) : null,
          campo("Nombre", entrada("nombre", { valor: p?.nombre, requerido: true, maxlength: 120 })),
          campo("NIT", entrada("nit", { valor: p?.nit, maxlength: 20 }), "Opcional. Se usa al radicar y en el RIPS."),
          h("div", { class: "acciones derecha" }, h("button", { class: "btn", type: "button", onclick: cerrar }, "Cancelar"), guardar));
        cuerpo.append(form);
      },
    });
  }

  function formConvenio(p, c) {
    const nuevo = !c;
    abrirDialogo({
      titulo: nuevo ? `Nuevo convenio con ${p.nombre}` : `Editar convenio ${c.nombre}`,
      construir: (cuerpo, cerrar) => {
        const mensaje = h("div");
        const guardar = h("button", { class: "btn btn-primario", type: "submit" }, "Guardar");
        const ejemplo = h("p", { class: "valor-previo" });
        const marca = h("input", { type: "checkbox", name: "requiere_autorizacion", checked: c?.requiere_autorizacion });
        const form = h("form", {
          onsubmit: async (e) => {
            e.preventDefault();
            guardar.disabled = true;
            const d = datosDe(form);
            const cuerpoPeticion = {
              nombre: d.nombre,
              porcentaje_tarifa: Number(d.porcentaje_tarifa),
              copago_porcentaje: Number(d.copago_porcentaje),
              cuota_moderadora: Number(d.cuota_moderadora),
              requiere_autorizacion: marca.checked,
            };
            try {
              if (nuevo) await api.post(`/api/pagadores/${p.id}/convenios`, cuerpoPeticion);
              else await api.put(`/api/convenios/${c.id}`, cuerpoPeticion);
              cerrar();
              aviso(nuevo ? "Convenio agregado." : "Cambios guardados.");
              cargar();
            } catch (error) {
              mensaje.replaceChildren(alerta(error));
              guardar.disabled = false;
            }
          },
        }, mensaje,
          campo("Nombre del convenio", entrada("nombre", { valor: c?.nombre, requerido: true, maxlength: 120 }), "Ej.: Régimen contributivo"),
          h("div", { class: "rejilla-campos" },
            campo("Tarifa pactada (% de la tarifa base)", entrada("porcentaje_tarifa", { tipo: "number", valor: c?.porcentaje_tarifa ?? 100, requerido: true, min: 1, max: 300, step: 1 }), "100 = tarifa completa; 90 = 10 % menos."),
            campo("Copago (% de la cuenta)", entrada("copago_porcentaje", { tipo: "number", valor: c?.copago_porcentaje ?? 0, requerido: true, min: 0, max: 100, step: 1 }), "Lo paga el paciente."),
            campo("Cuota moderadora (pesos)", entrada("cuota_moderadora", { tipo: "number", valor: c?.cuota_moderadora ?? 0, requerido: true, min: 0, step: 1, inputmode: "numeric" }), "Se cobra una vez por ingreso.")),
          h("label", { class: "casilla" }, marca, h("span", {}, "Exige número de autorización al admitir al paciente")),
          ejemplo,
          h("div", { class: "acciones derecha" }, h("button", { class: "btn", type: "button", onclick: cerrar }, "Cancelar"), guardar));
        const actualizar = () => {
          const pct = Number(form.elements.porcentaje_tarifa.value) || 0;
          const cop = Number(form.elements.copago_porcentaje.value) || 0;
          const cuota = Number(form.elements.cuota_moderadora.value) || 0;
          const total = Math.floor((100000 * pct + 50) / 100);
          const paciente = Math.min(total, Math.floor((total * cop + 50) / 100) + cuota);
          ejemplo.replaceChildren("Ejemplo con un servicio de ", h("b", { class: "num" }, pesos(100000)), ": se factura ",
            h("b", { class: "num" }, pesos(total)), "; paciente ", h("b", { class: "num" }, pesos(paciente)),
            " y pagador ", h("b", { class: "num" }, pesos(total - paciente)), ".");
        };
        form.addEventListener("input", actualizar);
        cuerpo.append(form);
        actualizar();
      },
    });
  }

  raiz.append(
    h("header", { class: "encabezado" },
      h("div", {}, h("h1", {}, "Pagadores y convenios"),
        h("p", {}, "Quién paga cada atención y en qué condiciones: tarifa pactada, copago, cuota moderadora y autorización.")),
      h("button", { class: "btn btn-primario", type: "button", onclick: () => formPagador(null) }, "Agregar pagador")),
    zona);
  await cargar();
}
