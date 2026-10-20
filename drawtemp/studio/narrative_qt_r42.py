"""R42.B1 Narrative Graph Qt: inspect/edit canonical dialogue with shared Undo/Redo.

This is an explicit opt-in authoring surface. No parallel JSON store, runtime
mutation or timer; preview uses the same validation as Player load.
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtWidgets import (
    QDialog, QGraphicsScene, QGraphicsView, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QAbstractItemView,
)

from drawtemp.studio.narrative_workbench_r42 import NarrativeWorkbench
from drawtemp.studio.narrative_debugger_r42 import NarrativeDebugger
from drawtemp.sdk.authoring import AuthoringError


class NarrativeGraphView(QGraphicsView):
    selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('r42-narrative-graph')
        self.setAccessibleName('Graphe des scènes narratives R42')
        self.setScene(QGraphicsScene(self))
        self.setMinimumWidth(340)

    def draw_graph(self, projection, selection=''):
        scene = self.scene()
        scene.clear()
        positions = {}
        for index, node in enumerate(projection['nodes']):
            column, row = divmod(index, 4)
            x, y = 24 + column * 230, 26 + row * 118
            positions[node['id']] = (x, y)
            rect = scene.addRect(
                0, 0, 195, 79,
                QPen(QColor('#ffd58a' if node['id'] == selection else '#8ca9d0'), 3),
                QBrush(QColor('#234761')))
            rect.setPos(x, y)
            rect.setData(0, node['id'])
            label = scene.addText(node['title'][:45] + '\n' + node['id'])
            label.setDefaultTextColor(QColor('#ffffff'))
            label.setParentItem(rect)
            label.setPos(8, 7)
        for edge in projection['edges']:
            if edge['from'] not in positions or edge['to'] not in positions:
                continue
            x1, y1 = positions[edge['from']]
            x2, y2 = positions[edge['to']]
            line = scene.addLine(x1 + 180, y1 + 65, x2 + 12, y2 + 14,
                                 QPen(QColor('#6bd9b6'), 2))
            line.setZValue(-1)
        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-20, -20, 20, 20))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.pos())
            while item is not None:
                identifier = item.data(0)
                if isinstance(identifier, str):
                    self.selected.emit(identifier)
                    break
                item = item.parentItem()
        super().mousePressEvent(event)


class NarrativeStudioDialog(QDialog):
    updated = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.workbench = NarrativeWorkbench(session)
        self._selected = ''
        self._plan = None
        self._dirty = False
        self.debugger = None
        self.setObjectName('r42-narrative-dialog')
        self.setWindowTitle('DrawTemp · Narrative Studio R42.B1')
        self.resize(1160, 780)
        root = QVBoxLayout(self)
        self.status = QLabel('Choisissez une scène. Aperçu et application sont séparés.')
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        toolbar = QHBoxLayout()
        self.buttons = {}
        for key, title, action in (
            ('template', 'Modèle VS-42', self.preview_template),
            ('migrate', 'Migrer v1 → v2', self.preview_migration),
            ('new', 'Créer scène', self.preview_new_scene),
            ('link', 'Relier un choix', self.preview_link),
            ('state', 'Déclarer variable', self.preview_state),
            ('subgraph', 'Sous-graphe', self.preview_subgraph),
            ('preview', 'Prévisualiser lignes', self.preview_lines),
            ('apply', 'Appliquer', self.apply_preview),
            ('undo', 'Annuler', self.undo),
            ('redo', 'Rétablir', self.redo),
        ):
            button = QPushButton(title)
            button.setObjectName('r42-' + key)
            button.clicked.connect(action)
            toolbar.addWidget(button)
            self.buttons[key] = button
        root.addLayout(toolbar)
        split = QSplitter(Qt.Horizontal)
        self.graph = NarrativeGraphView()
        self.graph.selected.connect(self.select_scene)
        split.addWidget(self.graph)
        editor = QWidget()
        form = QVBoxLayout(editor)
        self.heading = QLabel('Scène')
        form.addWidget(self.heading)
        self.lines = QTableWidget(0, 3)
        self.lines.setObjectName('r42-dialogue-lines')
        self.lines.setHorizontalHeaderLabels(['ID stable', 'Locuteur', 'Texte'])
        self.lines.setAccessibleName('Lignes de dialogue identifiées')
        self.lines.horizontalHeader().setStretchLastSection(True)
        self.lines.cellChanged.connect(self._invalidate)
        form.addWidget(self.lines, 2)
        controls = QHBoxLayout()
        for title, callback in (('Ajouter ligne', self.add_line),
                                ('Supprimer ligne', self.remove_line)):
            b = QPushButton(title)
            b.clicked.connect(callback)
            controls.addWidget(b)
        form.addLayout(controls)
        form.addWidget(QLabel('Choix, conditions et effets (lecture seule)'))
        self.choices = QPlainTextEdit()
        self.choices.setObjectName('r42-choice-inspector')
        self.choices.setReadOnly(True)
        form.addWidget(self.choices, 1)
        form.addWidget(QLabel('Références entrantes (source → usage)'))
        self.uses = QPlainTextEdit()
        self.uses.setReadOnly(True)
        form.addWidget(self.uses, 1)
        form.addWidget(QLabel('Variables déclarées (valeurs initiales)'))
        self.variables = QTableWidget(0, 5)
        self.variables.setHorizontalHeaderLabels(
            ['Nom', 'Type', 'Portée', 'Propriétaire', 'Initial'])
        self.variables.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.variables.horizontalHeader().setStretchLastSection(True)
        form.addWidget(self.variables, 1)
        split.addWidget(editor)
        split.setSizes([480, 680])
        root.addWidget(split, 1)
        debugbar = QHBoxLayout()
        self.debug_buttons = {}
        for key, title, action in (
            ('start', 'Démarrer le debugger', self.debug_start),
            ('audit', 'Auditer les chemins', self.audit_paths),
            ('break', 'Point d’arrêt', self.debug_breakpoint),
            ('next', 'Pas suivant', self.debug_step),
            ('choose', 'Tester un choix', self.debug_choose),
            ('forecast', 'Prévoir les effets', self.debug_forecast),
            ('reset', 'Arrêter le debugger', self.debug_reset),
        ):
            button = QPushButton(title)
            button.setObjectName('r42-debug-' + key)
            button.clicked.connect(action)
            debugbar.addWidget(button)
            self.debug_buttons[key] = button
        root.addLayout(debugbar)
        self.debug_output = QPlainTextEdit()
        self.debug_output.setObjectName('r42-debug-output')
        self.debug_output.setAccessibleName('Trace du debugger narratif isolé')
        self.debug_output.setReadOnly(True)
        self.debug_output.setMaximumHeight(170)
        root.addWidget(self.debug_output)
        self.refresh()

    def _invalidate(self, *_):
        self._plan = None
        self._dirty = True
        self.buttons['apply'].setEnabled(False)

    def _offer(self, plan, text):
        self._plan = plan
        self._dirty = False
        self.buttons['apply'].setEnabled(True)
        self.status.setText(text + ' — Aucun changement enregistré avant Appliquer.')

    def refresh(self, prefer=''):
        doc = self.workbench.document()
        graph = self.workbench.graph()
        names = [s['id'] for s in doc.get('scenes', [])]
        chosen = prefer or self._selected
        self._selected = chosen if chosen in names else (names[0] if names else '')
        self.graph.draw_graph(graph, self._selected)
        self.buttons['migrate'].setEnabled(bool(names) and graph['version'] == 1)
        for key in ('new', 'state', 'subgraph', 'preview'):
            self.buttons[key].setEnabled(graph['version'] == 2)
        self.buttons['link'].setEnabled(bool(self._selected))
        self.buttons['apply'].setEnabled(False)
        self._plan = None
        self._dirty = False
        if self.debugger is not None and (
                self.debugger.source_revision != self.workbench.session.revision):
            self.debugger = None
            self.debug_output.setPlainText(
                'Le projet a changé : debugger arrêté. Démarrez une nouvelle simulation.')
        self._display_selected()

    def select_scene(self, scene_id):
        if self._dirty or self._plan is not None:
            answer = QMessageBox.question(
                self, 'Modifications non appliquées',
                'Abandonner les lignes non appliquées ?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
        self._selected = scene_id
        self._plan = None
        self._dirty = False
        self._display_selected()
        self.graph.draw_graph(self.workbench.graph(), scene_id)
        self.buttons['apply'].setEnabled(False)

    def _display_selected(self):
        self.lines.blockSignals(True)
        self.lines.setRowCount(0)
        self.choices.clear()
        self.uses.clear()
        info = None
        if self._selected:
            info = self.workbench.inspect(self._selected)
            scene = info['scene']
            self.heading.setText(scene['title'] + '  [' + self._selected + ']')
            for line in scene.get('lines', []):
                self._insert(line['id'], line['speaker'], line['text'])
            self.choices.setPlainText('\n'.join(
                c['id'] + ': ' + c['label'] +
                (' → ' + c['next_scene'] if 'next_scene' in c else ' → FIN') +
                ('  [condition]' if 'when' in c else '') +
                ('  [effets: ' + ','.join(e['kind'] for e in c['effects']) + ']'
                 if c.get('effects') else '')
                for c in scene['choices']))
            self.uses.setPlainText('\n'.join(
                (r.get('scene', r.get('source', 'source')) + ' : ' +
                 r.get('choice', r.get('id', '')))
                for r in info['incoming']) or 'Aucune référence entrante')
        else:
            self.heading.setText('Aucune scène narrative')
        self.variables.setRowCount(0)
        for spec in self.workbench.document().get('state', []):
            index = self.variables.rowCount()
            self.variables.insertRow(index)
            for column, value in enumerate(
                (spec['id'], spec['kind'], spec['scope'],
                 spec['owner'], str(spec['initial']))):
                self.variables.setItem(index, column, QTableWidgetItem(value))
        self.lines.blockSignals(False)

    def _insert(self, identifier, speaker, text):
        row = self.lines.rowCount()
        self.lines.insertRow(row)
        for column, value in enumerate((identifier, speaker, text)):
            self.lines.setItem(row, column, QTableWidgetItem(value))

    def add_line(self):
        if not self._selected or self.workbench.graph()['version'] != 2:
            return
        current = {self.lines.item(i, 0).text()
                   for i in range(self.lines.rowCount())}
        for index in range(1, 33):
            candidate = 'line_' + str(index).zfill(3)
            if candidate not in current:
                self._insert(candidate, '', 'Nouveau dialogue')
                self._invalidate()
                return
        QMessageBox.warning(self, 'Limite', 'Maximum de 32 lignes par scène.')

    def remove_line(self):
        if self.lines.rowCount() <= 1:
            QMessageBox.warning(self, 'Dialogue', 'Une scène conserve au moins une ligne.')
            return
        index = self.lines.currentRow()
        if index < 0:
            return
        self.lines.removeRow(index)
        self._invalidate()

    def preview_lines(self):
        try:
            rows = []
            for row in range(self.lines.rowCount()):
                rows.append({
                    'id': self.lines.item(row, 0).text(),
                    'speaker': self.lines.item(row, 1).text(),
                    'text': self.lines.item(row, 2).text()})
            plan = self.workbench.preview_lines(self._selected, rows)
            self._offer(plan, 'Lignes validées, prêtes à être appliquées')
        except (AuthoringError, ValueError, TypeError, AttributeError) as exc:
            QMessageBox.warning(self, 'Validation narrative', str(exc))

    def preview_template(self):
        """Never overwrite a Studio document without a separate explicit Apply."""
        if self._dirty or self._plan is not None:
            QMessageBox.warning(
                self, 'Modèle VS-42',
                'Appliquez ou abandonnez les modifications en cours.')
            return
        confirm = QMessageBox.question(
            self, 'Modèle VS-42',
            'Prévisualiser le remplacement du Contenu et du Projet en mémoire '
            'par la quête « La loyauté du capitaine » ? '
            'Le remplacement ne sera effectif qu’en cliquant sur Appliquer ; '
            'Undo pourra le restaurer.',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return
        try:
            self._offer(self.workbench.preview_captain_slice(),
                        'Modèle VS-42 validé (Content + GameProject)')
        except (AuthoringError, ValueError) as exc:
            QMessageBox.warning(self, 'Modèle VS-42', str(exc))

    def preview_migration(self):
        try:
            self._offer(self.workbench.preview_migrate(), 'Migration explicite v2 validée')
        except (AuthoringError, ValueError) as exc:
            QMessageBox.warning(self, 'Migration', str(exc))

    def preview_new_scene(self):
        identifier, ok = QInputDialog.getText(self, 'Scène', 'ID stable de la scène')
        if not ok:
            return
        title, ok = QInputDialog.getText(self, 'Scène', 'Titre')
        if not ok:
            return
        text, ok = QInputDialog.getMultiLineText(self, 'Scène', 'Première réplique')
        if not ok:
            return
        try:
            plan = self.workbench.preview_create_scene(
                identifier, title, '', text)
            self._offer(plan, 'Création de scène validée')
        except (AuthoringError, ValueError) as exc:
            QMessageBox.warning(self, 'Scène', str(exc))

    def preview_link(self):
        doc = self.workbench.document()
        scene = next((s for s in doc.get('scenes', [])
                      if s['id'] == self._selected), None)
        if scene is None:
            return
        ids = [c['id'] for c in scene['choices']]
        choice, ok = QInputDialog.getItem(
            self, 'Lien de choix', 'Choix source', ids, 0, False)
        if not ok:
            return
        targets = ['(Fin)'] + [s['id'] for s in doc['scenes']]
        target, ok = QInputDialog.getItem(
            self, 'Lien de choix', 'Scène cible', targets, 0, False)
        if not ok:
            return
        try:
            self._offer(self.workbench.preview_link(
                self._selected, choice, '' if target == '(Fin)' else target),
                'Connexion validée avec les règles de cycles R9')
        except (AuthoringError, ValueError) as exc:
            QMessageBox.warning(self, 'Connexion', str(exc))

    def preview_subgraph(self):
        name, ok = QInputDialog.getText(self, 'Sous-graphe', 'Nom stable')
        if ok:
            try:
                self._offer(self.workbench.preview_subgraph(name, self._selected),
                            'Entrée de sous-graphe validée')
            except (AuthoringError, ValueError) as exc:
                QMessageBox.warning(self, 'Sous-graphe', str(exc))

    def preview_state(self):
        kind, ok = QInputDialog.getItem(self, 'Variable', 'Type',
                                        ['bool', 'int', 'relation', 'text'], 0, False)
        if not ok:
            return
        scope, ok = QInputDialog.getItem(self, 'Variable', 'Portée',
                                         ['campaign', 'scene', 'mission'], 0, False)
        if not ok:
            return
        project = self.workbench.session.snapshot().to_dict()
        candidates = {
            'campaign': [c['id'] for c in project['project']['campaigns']],
            'scene': [s['id'] for s in project['project'].get('story', {}).get('scenes', [])],
            'mission': [m['id'] for m in project['content']['missions']],
        }[scope]
        owner, ok = QInputDialog.getItem(
            self, 'Variable', 'Propriétaire canonique', candidates, 0, False)
        if not ok:
            return
        identifier, ok = QInputDialog.getText(
            self, 'Variable', 'Identifiant stable')
        if not ok:
            return
        default = 'false' if kind == 'bool' else ('0' if kind != 'text' else '')
        raw, ok = QInputDialog.getText(
            self, 'Variable', 'Valeur initiale', text=default)
        if not ok:
            return
        try:
            if kind == 'bool':
                if raw not in ('true', 'false'):
                    raise ValueError('Bool: true ou false')
                value = raw == 'true'
            elif kind in ('int', 'relation'):
                value = int(raw)
            else:
                value = raw
            self._offer(self.workbench.preview_state(
                identifier=identifier, kind=kind, scope=scope,
                owner=owner, initial=value), 'Variable typée validée')
        except (AuthoringError, ValueError) as exc:
            QMessageBox.warning(self, 'Variable', str(exc))

    def apply_preview(self):
        if self._plan is None:
            return
        try:
            self.workbench.apply(self._plan)
        except AuthoringError as exc:
            self._plan = None
            self.buttons['apply'].setEnabled(False)
            QMessageBox.warning(self, 'Application impossible', str(exc))
            return
        self.refresh()
        self.updated.emit()
        self.status.setText('Projet modifié en une transaction (Undo/Redo).')

    def undo(self):
        try:
            self.workbench.undo()
            self.refresh()
            self.updated.emit()
        except AuthoringError as exc:
            QMessageBox.warning(self, 'Annuler', str(exc))

    def redo(self):
        try:
            self.workbench.redo()
            self.refresh()
            self.updated.emit()
        except AuthoringError as exc:
            QMessageBox.warning(self, 'Rétablir', str(exc))

    def debug_start(self):
        """Create an isolated Simulation from the current committed project."""
        if self._dirty or self._plan is not None:
            QMessageBox.warning(self, 'Debugger',
                                'Appliquez ou abandonnez les modifications avant de tester.')
            return
        snapshot = self.workbench.session.snapshot().to_dict()
        campaigns = [row['id'] for row in snapshot['project']['campaigns']]
        if not campaigns:
            QMessageBox.warning(self, 'Debugger', 'Aucune campagne configurée.')
            return
        campaign, ok = QInputDialog.getItem(
            self, 'Debugger narratif', 'Campagne', campaigns, 0, False)
        if not ok:
            return
        try:
            self.debugger = NarrativeDebugger(self.workbench.session, campaign)
            self.debug_render()
        except Exception as exc:
            self.debugger = None
            QMessageBox.warning(self, 'Debugger narratif', str(exc))

    def debug_reset(self):
        self.debugger = None
        self.debug_output.setPlainText('Simulation isolée arrêtée.')

    def debug_render(self):
        if self.debugger is None:
            return
        try:
            report = self.debugger.report()
            self.debug_output.setPlainText(json.dumps({
                'scène': report['scene'],
                'réplique': report['line'],
                'pause_avant_effet': report['paused_on'],
                'choix': [{'id': choice['id'],
                           'autorisé': choice['available'],
                           'condition': choice['condition']}
                          for choice in report['choices']],
                'variables': report['flags'],
                'or': report['gold'],
                'dernière_transition': (report['events'][-1]
                                       if report['events'] else None),
                'décisions': report['history'],
                'isolé': report['isolated'],
                'replay_certifié': report['replay_verified'],
            }, ensure_ascii=False, indent=2))
            if report['scene'] and not self._dirty and self._plan is None:
                self.graph.draw_graph(self.workbench.graph(), report['scene'])
        except Exception as exc:
            QMessageBox.warning(self, 'Debugger narratif', str(exc))

    def debug_breakpoint(self):
        if self.debugger is None:
            return
        doc = self.workbench.document()
        scene = next((row for row in doc.get('scenes', [])
                      if row['id'] == self._selected), None)
        if scene is None:
            return
        choices = [row['id'] for row in scene['choices']]
        chosen, ok = QInputDialog.getItem(
            self, 'Point d’arrêt', 'Choix avant ses effets', choices, 0, False)
        if not ok:
            return
        try:
            key = (self._selected, chosen)
            enabled = key not in self.debugger.breakpoints
            self.debugger.breakpoint(*key, enabled=enabled)
            self.debug_render()
        except Exception as exc:
            QMessageBox.warning(self, 'Point d’arrêt', str(exc))

    def debug_step(self):
        if self.debugger is None:
            return
        try:
            self.debugger.step()
            self.debug_render()
        except Exception as exc:
            QMessageBox.warning(self, 'Pas narratif', str(exc))

    def debug_choose(self):
        if self.debugger is None:
            return
        try:
            options = [row['id'] for row in self.debugger.inspect()['choices']
                       if row['available']]
            if not options:
                QMessageBox.information(
                    self, 'Debugger', 'Avancez les répliques ou vérifiez les conditions.')
                return
            choice, ok = QInputDialog.getItem(
                self, 'Tester un choix', 'Choix disponible', options, 0, False)
            if ok:
                self.debugger.choose(choice)
                self.debug_render()
        except Exception as exc:
            QMessageBox.warning(self, 'Choix narratif', str(exc))

    def debug_forecast(self):
        """Read-only canonical consequence forecast; no debugger step or edit."""
        if self.debugger is None:
            return
        try:
            options = [row['id'] for row in self.debugger.inspect()['choices']
                       if row['available']]
            if not options:
                QMessageBox.information(
                    self, 'Prévision', 'Aucun choix autorisé à cette réplique.')
                return
            choice, ok = QInputDialog.getItem(
                self, 'Prévoir les effets', 'Choix', options, 0, False)
            if ok:
                forecast = self.debugger.preview_choice(choice)
                self.debug_output.setPlainText(
                    'Prévision isolée, aucun effet appliqué :\n' +
                    json.dumps(forecast, ensure_ascii=False, indent=2))
        except Exception as exc:
            QMessageBox.warning(self, 'Prévision narrative', str(exc))

    def audit_paths(self):
        """Bounded read-only R42.C graph check with concrete route witnesses."""
        if self._dirty or self._plan is not None:
            QMessageBox.warning(self, 'Audit narratif',
                                'Appliquez ou abandonnez les modifications avant l’audit.')
            return
        raw = self.workbench.session.snapshot().to_dict()
        campaigns = [item['id'] for item in raw['project']['campaigns']]
        campaign, ok = QInputDialog.getItem(
            self, 'Auditer les chemins', 'Campagne', campaigns, 0, False)
        if not ok:
            return
        try:
            self._audit_campaign(campaign)
        except Exception as exc:
            QMessageBox.warning(self, 'Audit narratif', str(exc))

    def _audit_campaign(self, campaign):
        """Headless-compatible internal Qt view adapter; never applies an edit."""
        from drawtemp.sdk.r42_reachability import audit_narrative
        from sporebound.model import Content
        from sporebound.game_project import GameProject
        from sporebound.tactical_rpg3 import authored_rules_for_document

        snapshot = self.workbench.session.snapshot().to_dict()
        content_data = snapshot['content']
        content = Content.from_dict(
            content_data, rules=authored_rules_for_document(content_data))
        project = GameProject.from_dict(snapshot['project'], content)
        required = tuple(project.campaign_flow.get('endings', {}))
        report = audit_narrative(
            content, project, campaign, expected_endings=required,
            min_reused_scenes=2, max_states=1024)
        self.debug_output.setPlainText(json.dumps({
            'succès': report['passed'],
            'campagne': campaign,
            'scènes_partagées': report['reused_scenes'],
            'états_explorés': report['explored_states'],
            'fins_et_chemins': {key: row['route']
                                for key, row in report['endings'].items()},
            'fins_manquantes': report['missing_endings'],
            'scènes_inaccessibles': report['dead_scenes'],
            'choix_bloqués_et_contre_exemples': report['dead_choices'],
            'limite_de_preuve': report['scope'],
            'replay_tactique_certifié': False,
            'export_player_certifié': False,
        }, ensure_ascii=False, indent=2))
        return report
