import { api } from "../api.js";
import { abrirDialogo, alerta, aviso, campo, areaTexto, debounce, entrada, h, seleccion, TIPOS_INGRESO } from "../ui.js";

// Formulario de admisión (ingreso). Si ya se conoce al paciente se muestra fijo; si no, se elige buscándolo.
export function abrirAdmision({ paciente = null, alCrear }) {
  abrirDialogo({
    titulo: "Ingresar paciente",
    ancho: true,
    construir: async (cuerpo, cerrar) => {
      let elegido = paciente;
      const mensaje = h("div");
      const zonaPaciente = h("div");
      const buscador = entrada("q", { tipo: "search", placeholder: "Documento o nombre", "aria-label": "Buscar paciente" });
      const resultados = h("ul", { class: "resultados" });
      const guardar = h("button", { class: "btn btn-primario", type: "submit" }, "Ingresar paciente");
      let medicos = [];
      try {
        medicos = await api.get("/api/medicos");
      } catch (error) {
        cuerpo.append(alerta(error));
        return;
      }

      function pintarPaciente() {
        if (elegido) {
          zonaPaciente.replaceChildren(h("div", { class: "paciente-elegido" },
            h("div", {}, h("b", {}, elegido.nombre_completo), h("span", { class: "num suave" }, ` · ${elegido.tipo_documento} ${elegido.numero_documento}`)),
            paciente ? null : h("button", { class: "btn btn-pequeno", type: "button", onclick: () => { elegido = null; pintarPaciente(); } }, "Cambiar")));
        } else {
          zonaPaciente.replaceChildren(campo("Paciente", buscador), resultados);
          buscarPaciente();
        }
      }

      async function buscarPaciente() {
        try {
          const lista = await api.get("/api/pacientes", { q: buscador.value.trim() });
          resultados.replaceChildren(...lista.slice(0, 6).map((p) => h("li", {},
            h("button", { type: "button", onclick: () => { elegido = p; pintarPaciente(); } },
              h("b", {}, p.nombre_completo), h("span", { class: "num" }, `${p.tipo_documento} ${p.numero_documento}`))),
          ));
          if (!lista.length) resultados.replaceChildren(h("li", { class: "suave" }, "No hay pacientes con ese dato."));
        } catch (error) {
          resultados.replaceChildren(h("li", {}, alerta(error)));
        }
      }
      buscador.addEventListener("input", debounce(buscarPaciente, 300));

      const form = h("form", {
        onsubmit: async (e) => {
          e.preventDefault();
          mensaje.replaceChildren();
          if (!elegido) {
            mensaje.replaceChildren(alerta("Elija al paciente que va a ingresar."));
            return;
          }
          guardar.disabled = true;
          try {
            const ingreso = await api.post("/api/ingresos", {
              paciente_id: elegido.id,
              medico_id: Number(form.elements.medico_id.value),
              tipo: form.elements.tipo.value,
              motivo: form.elements.motivo.value.trim(),
            });
            cerrar();
            aviso("Paciente ingresado. Ya se pueden registrar sus procedimientos.");
            alCrear(ingreso);
          } catch (error) {
            mensaje.replaceChildren(alerta(error));
            if (error.cuerpo?.ingreso_abierto_id) {
              const id = error.cuerpo.ingreso_abierto_id;
              mensaje.append(h("a", { class: "btn", href: `#/ingreso/${id}`, onclick: cerrar }, "Ver el ingreso abierto"));
            }
            guardar.disabled = false;
          }
        },
      },
        mensaje, zonaPaciente,
        h("div", { class: "rejilla-campos" },
          campo("Médico tratante", seleccion("medico_id", medicos.map((m) => [m.id, m.especialidad ? `${m.nombre_completo} · ${m.especialidad}` : m.nombre_completo]), medicos[0]?.id)),
          campo("Tipo de ingreso", seleccion("tipo", Object.entries(TIPOS_INGRESO), "AMBULATORIO"))),
        campo("Motivo del ingreso", areaTexto("motivo", "", { rows: 2, required: true, maxlength: 500 })),
        h("div", { class: "acciones derecha" }, h("button", { class: "btn", type: "button", onclick: cerrar }, "Cancelar"), guardar));
      cuerpo.append(form);
      pintarPaciente();
    },
  });
}
