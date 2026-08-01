import 'package:flutter/material.dart';

import 'client_models.dart';
import 'client_state.dart';

Future<void> showHistorySearchDialog(
  BuildContext context,
  SuMeMeClientState state,
) async {
  await showDialog<void>(
    context: context,
    builder: (BuildContext context) => _HistorySearchDialog(state: state),
  );
}

class _HistorySearchDialog extends StatefulWidget {
  const _HistorySearchDialog({required this.state});

  final SuMeMeClientState state;

  @override
  State<_HistorySearchDialog> createState() => _HistorySearchDialogState();
}

class _HistorySearchDialogState extends State<_HistorySearchDialog> {
  final TextEditingController _query = TextEditingController();
  List<ChatMessage> _results = <ChatMessage>[];
  DateTime? _start;
  DateTime? _end;
  bool _searching = false;
  bool _searched = false;

  @override
  void dispose() {
    _query.dispose();
    super.dispose();
  }

  Future<void> _pickStart() async {
    final DateTime? result = await showDatePicker(
      context: context,
      firstDate: DateTime(2020),
      lastDate: DateTime.now(),
      initialDate: _start ?? DateTime.now(),
    );
    if (result != null) setState(() => _start = result);
  }

  Future<void> _pickEnd() async {
    final DateTime? result = await showDatePicker(
      context: context,
      firstDate: _start ?? DateTime(2020),
      lastDate: DateTime.now(),
      initialDate: _end ?? DateTime.now(),
    );
    if (result != null) {
      setState(() => _end = DateTime(result.year, result.month, result.day, 23, 59, 59));
    }
  }

  Future<void> _search() async {
    setState(() {
      _searching = true;
      _searched = true;
    });
    final String keyword = _query.text.trim();
    final List<ChatMessage> local = await widget.state.searchLocalHistory(
      keyword: keyword,
      start: _start,
      end: _end,
    );
    if (keyword.isNotEmpty) await widget.state.searchMemory(keyword);
    if (!mounted) return;
    setState(() {
      _results = local.reversed.toList(growable: false);
      _searching = false;
    });
  }

  String _date(DateTime value) {
    String two(int number) => number.toString().padLeft(2, '0');
    return '${value.year}-${two(value.month)}-${two(value.day)} '
        '${two(value.hour)}:${two(value.minute)}';
  }

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    final double width = MediaQuery.sizeOf(context).width;
    return Dialog(
      insetPadding: EdgeInsets.symmetric(
        horizontal: width < 600 ? 14 : 40,
        vertical: 24,
      ),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 760, maxHeight: 760),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(22, 20, 22, 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              Row(
                children: <Widget>[
                  Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      color: colors.primaryContainer,
                      borderRadius: BorderRadius.circular(13),
                    ),
                    child: Icon(Icons.manage_search_rounded, color: colors.primary),
                  ),
                  const SizedBox(width: 12),
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          '查找聊天与记忆',
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
                        ),
                        Text('支持关键词、时间范围和长期记忆语义召回'),
                      ],
                    ),
                  ),
                  IconButton(
                    onPressed: () => Navigator.pop(context),
                    icon: const Icon(Icons.close_rounded),
                  ),
                ],
              ),
              const SizedBox(height: 18),
              TextField(
                controller: _query,
                autofocus: true,
                textInputAction: TextInputAction.search,
                onSubmitted: (_) => _search(),
                decoration: InputDecoration(
                  hintText: '输入聊天关键词或想找的记忆，例如“上次服务器怎么配置的”',
                  prefixIcon: const Icon(Icons.search_rounded),
                  suffixIcon: FilledButton.tonal(
                    onPressed: _searching ? null : _search,
                    child: const Text('查找'),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: <Widget>[
                  FilterChip(
                    selected: _start != null,
                    label: Text(_start == null
                        ? '开始时间'
                        : '从 ${_start!.year}-${_start!.month}-${_start!.day}'),
                    avatar: const Icon(Icons.calendar_today_outlined, size: 16),
                    onSelected: (_) => _pickStart(),
                    onDeleted: _start == null ? null : () => setState(() => _start = null),
                  ),
                  FilterChip(
                    selected: _end != null,
                    label: Text(_end == null
                        ? '结束时间'
                        : '到 ${_end!.year}-${_end!.month}-${_end!.day}'),
                    avatar: const Icon(Icons.event_available_outlined, size: 16),
                    onSelected: (_) => _pickEnd(),
                    onDeleted: _end == null ? null : () => setState(() => _end = null),
                  ),
                  if (_start != null || _end != null)
                    ActionChip(
                      avatar: const Icon(Icons.restart_alt_rounded, size: 18),
                      label: const Text('清除时间'),
                      onPressed: () => setState(() {
                        _start = null;
                        _end = null;
                      }),
                    ),
                ],
              ),
              const SizedBox(height: 12),
              if (_searching) const LinearProgressIndicator(),
              Expanded(
                child: !_searched
                    ? _EmptySearch(colors: colors)
                    : ListView(
                        children: <Widget>[
                          if (widget.state.memoryResult.isNotEmpty) ...<Widget>[
                            const _SectionLabel(
                              icon: Icons.auto_awesome_rounded,
                              label: '长期记忆召回',
                            ),
                            Container(
                              margin: const EdgeInsets.only(bottom: 16),
                              padding: const EdgeInsets.all(16),
                              decoration: BoxDecoration(
                                color: colors.primaryContainer.withValues(alpha: .45),
                                borderRadius: BorderRadius.circular(16),
                              ),
                              child: SelectableText(widget.state.memoryResult),
                            ),
                          ],
                          _SectionLabel(
                            icon: Icons.history_rounded,
                            label: '本机聊天记录 · ${_results.length} 条',
                          ),
                          if (_results.isEmpty)
                            const Padding(
                              padding: EdgeInsets.symmetric(vertical: 32),
                              child: Center(child: Text('没有符合条件的聊天记录')),
                            )
                          else
                            ..._results.map((ChatMessage message) => Card(
                                  elevation: 0,
                                  margin: const EdgeInsets.only(bottom: 8),
                                  child: ListTile(
                                    leading: CircleAvatar(
                                      backgroundColor: message.role == 'user'
                                          ? colors.primaryContainer
                                          : colors.secondaryContainer,
                                      child: Icon(
                                        message.role == 'user'
                                            ? Icons.person_outline_rounded
                                            : Icons.auto_awesome_rounded,
                                      ),
                                    ),
                                    title: Text(
                                      message.text,
                                      maxLines: 3,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                    subtitle: Text(_date(message.createdAt)),
                                  ),
                                )),
                        ],
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(2, 10, 2, 8),
        child: Row(
          children: <Widget>[
            Icon(icon, size: 18),
            const SizedBox(width: 7),
            Text(label, style: const TextStyle(fontWeight: FontWeight.w700)),
          ],
        ),
      );
}

class _EmptySearch extends StatelessWidget {
  const _EmptySearch({required this.colors});

  final ColorScheme colors;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(30),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Icon(Icons.search_rounded, size: 58, color: colors.outline),
              const SizedBox(height: 12),
              const Text(
                '查找一段过去的聊天或记忆',
                style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 6),
              Text(
                '输入关键词后会同时查询本机完整时间线和服务端长期记忆。',
                textAlign: TextAlign.center,
                style: TextStyle(color: colors.onSurfaceVariant),
              ),
            ],
          ),
        ),
      );
}
