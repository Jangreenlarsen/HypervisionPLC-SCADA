// Danske tekster til SVG-Edit i Tegn (v0.92.0). SVG-Edit 7 understøtter ikke dansk (det er ikke på dens liste over
// sprog, og den medfølgende danske fil er gammel og halvt engelsk), så editoren kørte på engelsk. Disse tekster lægges
// oven på de engelske ved opstart (manglende nøgler falder tilbage til engelsk). Genvejstasten vises af editoren selv.

export const DA = {
  common: {
    ok: 'OK', cancel: 'Annullér', key_backspace: 'Backspace', key_del: 'Delete', key_down: 'Ned', key_up: 'Op',
    more_opts: 'Flere valg', url: 'URL', width: 'Bredde', height: 'Højde',
  },
  ui: {
    toggle_stroke_tools: 'Vis/skjul flere stregvalg',
    palette_info: 'Klik for at skifte fyldfarve — Shift+klik for at skifte stregfarve',
    zoom_level: 'Zoom (Ctrl + musehjul)', panel: 'Lag', panel_action: 'Vis/skjul lag',
    quality: 'Kvalitet:', pathNodeTooltip: 'Træk punktet for at flytte det — dobbeltklik for at skifte mellem lige og buet',
    pathCtrlPtTooltip: 'Træk håndtaget for at bøje kurven', pick_stroke_paint_opacity: 'Vælg stregfarve og gennemsigtighed',
    pick_fill_paint_opacity: 'Vælg fyldfarve og gennemsigtighed', group_identify_label: 'Gruppens navn',
    export_type_label: 'Vælg billedtype:',
  },
  layers: {
    layer: 'Lag', layers: 'Lag', del: 'Slet lag', move_down: 'Flyt laget ned', new: 'Nyt lag', rename: 'Omdøb lag',
    move_up: 'Flyt laget op', dupe: 'Kopiér lag …', merge_down: 'Flet med laget under', merge_all: 'Flet alle lag',
    move_elems_to: 'Flyt til lag:', move_selected: 'Flyt det valgte til et andet lag',
  },
  tools: {
    main_menu: 'Menu', fitToContent: 'Tilpas til indholdet', fit_to_all: 'Zoom til alt indhold', fit_to_canvas: 'Zoom til hele tegningen',
    fit_to_layer_content: 'Zoom til lagets indhold', fit_to_sel: 'Zoom til det valgte',
    align_relative_to: 'Justér i forhold til …', relativeTo: 'i forhold til:', page: 'tegningen', largest_object: 'største element',
    selected_objects: 'de valgte', smallest_object: 'mindste element', export_img: 'Eksportér', import_doc: 'Importér SVG',
    align_to_page: 'Placér på tegningen', align_bottom: 'Justér i bunden', align_center: 'Centrér vandret',
    align_left: 'Justér til venstre', align_middle: 'Centrér lodret', align_right: 'Justér til højre', align_top: 'Justér i toppen',
    align_distrib_horiz: 'Fordel jævnt vandret', align_distrib_verti: 'Fordel jævnt lodret',
    mode_select: 'Vælg og flyt', mode_fhpath: 'Frihåndstegning', mode_line: 'Streg', mode_rect: 'Rektangel',
    mode_square: 'Kvadrat', mode_fhrect: 'Frihånds-rektangel', mode_ellipse: 'Ellipse', mode_circle: 'Cirkel',
    mode_fhellipse: 'Frihånds-ellipse', mode_path: 'Sti (rør og figurer med knæk/kurver)', mode_text: 'Tekst',
    mode_image: 'Billede', mode_zoom: 'Zoom (træk en ramme)',
    undo: 'Fortryd', redo: 'Gentag', tool_source: 'Vis/ret SVG-koden', wireframe_mode: 'Vis kun konturer',
    clone: 'Duplikér', del: 'Slet', group_elements: 'Saml i gruppe', make_link: 'Lav et link', set_link_url: 'Linkets adresse (tomt fjerner det)',
    to_path: 'Gør til sti (så punkterne kan rettes)', reorient_path: 'Ret stiens retning ind', flip_horizontal: 'Spejlvend vandret',
    flip_vertical: 'Spejlvend lodret', ungroup: 'Opløs gruppen', docprops: 'Tegningens egenskaber', editor_homepage: 'SVG-Edits hjemmeside',
    move_bottom: 'Læg bagerst', move_top: 'Læg forrest', node_clone: 'Kopiér punktet', node_delete: 'Slet punktet',
    node_link: 'Lås kurvehåndtagene sammen', add_subpath: 'Tilføj en del-sti', openclose_path: 'Åbn/luk stien',
    source_save: 'Brug ændringerne', cut: 'Klip', copy: 'Kopiér', paste: 'Indsæt', paste_in_place: 'Indsæt på samme sted',
    delete: 'Slet', group: 'Saml i gruppe', move_front: 'Læg forrest', move_up: 'Flyt et lag frem', move_down: 'Flyt et lag tilbage',
    move_back: 'Læg bagerst', tool_unlink_use: 'Gør til en selvstændig kopi', ellipse_circle_tool: 'Ellipse / cirkel',
    square_rect_tool: 'Rektangel / kvadrat', connector_no_arrow: 'Ingen pil', bkgnd_color_opac: 'Baggrundsfarve',
  },
  properties: {
    id: 'Elementets id (bruges af bindinger og opsætninger)', fill_color: 'Fyldfarve', stroke_color: 'Stregfarve',
    stroke_style: 'Stregtype (hel, stiplet …)', stroke_width: 'Stregbredde (Shift+klik: i trin af 0,1)', pos_x: 'Vandret placering (x)',
    pos_y: 'Lodret placering (y)', linecap_butt: 'Stregens ender: lige', linecap_round: 'Stregens ender: runde',
    linecap_square: 'Stregens ender: firkantede', linejoin_bevel: 'Knæk: skåret', linejoin_miter: 'Knæk: spidst', linejoin_round: 'Knæk: rundt',
    angle: 'Drejning (grader)', blur: 'Sløring', opacity: 'Gennemsigtighed (%)',
    circle_cx: 'Cirklens midte (x)', circle_cy: 'Cirklens midte (y)', circle_r: 'Cirklens radius',
    ellipse_cx: 'Ellipsens midte (x)', ellipse_cy: 'Ellipsens midte (y)', ellipse_rx: 'Ellipsens bredde-radius', ellipse_ry: 'Ellipsens højde-radius',
    line_x1: 'Stregens start (x)', line_x2: 'Stregens slut (x)', line_y1: 'Stregens start (y)', line_y2: 'Stregens slut (y)',
    rect_height: 'Højde', rect_width: 'Bredde', corner_radius: 'Runde hjørner (radius)', image_width: 'Billedets bredde',
    image_height: 'Billedets højde', image_url: 'Billedets adresse', node_x: 'Punktets placering (x)', node_y: 'Punktets placering (y)',
    seg_type: 'Linjestykket: lige eller buet', straight_segments: 'Lige', curve_segments: 'Buet', text_contents: 'Tekst',
    font_family_label: 'Skrift:', font_family: 'Skrifttype', font_size: 'Skriftstørrelse', bold: 'Fed', italic: 'Kursiv',
    text_decoration_underline: 'Understreget', text_decoration_linethrough: 'Gennemstreget', text_decoration_overline: 'Overstreget',
    text_anchor_start: 'Venstrestil', text_anchor_middle: 'Centrér', text_anchor_end: 'Højrestil', text_letter_spacing: 'Afstand mellem bogstaver',
    text_word_spacing: 'Afstand mellem ord', text_length: 'Tekstens bredde (strækkes til)', text_length_adjust: 'Stræk',
    text_length_adjust_spacing: 'Kun mellemrum', text_length_adjust_spacing_and_glyphs: 'Mellemrum og bogstaver',
    r_label: 'r', x_label: 'x', y_label: 'y', x1_label: 'x1', y1_label: 'y1', x2_label: 'x2', y2_label: 'y2', rx_label: 'rx', ry_label: 'ry',
    cx_label: 'cx', cy_label: 'cy', w_label: 'b', h_label: 'h', id_label: 'id', class_label: 'klasse', label: 'navn', class: 'CSS-klasse',
  },
};

/** Udvidelsernes egne tekster (navnerum = udvidelsens navn). */
export const DA_EXT = {
  eyedropper: { name: 'pipette', buttons: [{ title: 'Pipette — kopiér farverne fra ét element til et andet', key: 'I' }] },
  panning: { name: 'Panorér', buttons: [{ title: 'Flyt udsnittet (eller hold mellemrum nede og træk)', key: '[mellemrum / musehjul + træk]' }] },
  polystar: {
    name: 'stjerne', title: 'Stjerne / polygon',
    buttons: [{ title: 'Stjerne' }, { title: 'Polygon (mangekant)' }],
    contextTools: [{ title: 'Antal spidser', label: 'spidser' }, { title: 'Hvor spidse', label: 'spidshed' }, { title: 'Drej spidserne', label: 'drej' }, { title: 'Antal sider', label: 'sider' }],
  },
  shapes: {
    loading: 'Henter …',
    categories: {
      basic: 'Grundformer', object: 'Ting', symbol: 'Symboler', arrow: 'Pile', flowchart: 'Rutediagram', animal: 'Dyr', game: 'Kort og skak',
      dialog_balloon: 'Talebobler', electronics: 'Elektronik', math: 'Matematik', music: 'Musik', misc: 'Diverse',
      raphael_1: 'raphaeljs.com sæt 1', raphael_2: 'raphaeljs.com sæt 2',
    },
    buttons: [{ title: 'Former (pile, stjerner, talebobler …)' }],
  },
};

/** Dybt flet: `over` oven på `base` (arrays elementvis). */
export function merge(base, over) {
  if (Array.isArray(over)) return over.map((v, i) => merge(Array.isArray(base) ? base[i] : undefined, v));
  if (over && typeof over === 'object') {
    const out = { ...(base && typeof base === 'object' && !Array.isArray(base) ? base : {}) };
    for (const [k, v] of Object.entries(over)) out[k] = merge(out[k], v);
    return out;
  }
  return over === undefined ? base : over;
}
