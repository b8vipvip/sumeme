import 'dart:io';
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import 'client_api.dart';
import 'client_models.dart';
import 'client_state.dart';

class SuMeMeLibraryPage extends StatefulWidget {
  const SuMeMeLibraryPage({super.key, required this.state});

  final SuMeMeClientState state;

  @override
  State<SuMeMeLibraryPage> createState() => _SuMeMeLibraryPageState();
}

class _SuMeMeLibraryPageState extends State<SuMeMeLibraryPage> {
  static const double _itemExtent = 88;
  final TextEditingController _search = TextEditingController();
  final ScrollController _scroll = ScrollController();
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();
    _search.text = widget.state.libraryQuery;
    _scroll.addListener(_syncTimeline);
    if (widget.state.libraryItems.isEmpty) {
      WidgetsBinding.instance.addPostFrameCallback((_) => widget.state.refreshLibrary());
    }
  }

  @override
  void dispose() {
    _search.dispose();
    _scroll
      ..removeListener(_syncTimeline)
      ..dispose();
    super.dispose();
  }

  void _syncTimeline() {
    final List<LibraryItem> items = widget.state.filteredLibraryItems;
    if (items.isEmpty) return;
    final int index = (_scroll.offset / _itemExtent).round().clamp(0, items.length - 1);
    if (index != _currentIndex && mounted) setState(() => _currentIndex = index);
  }

  void _jumpTo(int index) {
    final List<LibraryItem> items = widget.state.filteredLibraryItems;
    if (items.isEmpty) return;
    final int target = index.clamp(0, items.length - 1);
    setState(() => _currentIndex = target);
    if (_scroll.hasClients) {
      _scroll.animateTo(
        (target * _itemExtent).clamp(0, _scroll.position.maxScrollExtent),
        duration: const Duration(milliseconds: 260),
        curve: Curves.easeOutCubic,
      );
    }
  }

  Future<void> _pickFiles() async {
    final FilePickerResult? selection = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      type: FileType.any,
      withData: true,
    );
    if (selection == null) return;
    final List<UploadFileData> files = <UploadFileData>[];
    for (final PlatformFile file in selection.files) {
      Uint8List? bytes = file.bytes;
      if (bytes == null && file.path != null) bytes = await File(file.path!).readAsBytes();
      if (bytes == null) continue;
      files.add(UploadFileData(
        name: file.name,
        bytes: bytes,
        mimeType: _mime(file.name),
      ));
    }
    await widget.state.uploadFiles(files);
  }

  String _mime(String name) {
    final String extension = name.split('.').last.toLowerCase();
    return switch (extension) {
      'png' => 'image/png',
      'jpg' || 'jpeg' => 'image/jpeg',
      'webp' => 'image/webp',
      'gif' => 'image/gif',
      'pdf' => 'application/pdf',
      'txt' => 'text/plain',
      'md' => 'text/markdown',
      'json' => 'application/json',
      'csv' => 'text/csv',
      'mp3' => 'audio/mpeg',
      'wav' => 'audio/wav',
      'mp4' => 'video/mp4',
      _ => 'application/octet-stream',
    };
  }

  String _date(DateTime value) {
    String two(int number) => number.toString().padLeft(2, '0');
    return '${value.year}-${two(value.month)}-${two(value.day)} '
        '${two(value.hour)}:${two(value.minute)}';
  }

  String _size(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    if (bytes < 1024 * 1024 * 1024) {
      return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    }
    return '${(bytes / (1024 * 1024 * 1024)).toStringAsFixed(1)} GB';
  }

  IconData _icon(String type) {
    if (type.startsWith('image/')) return Icons.image_outlined;
    if (type.startsWith('video/')) return Icons.movie_outlined;
    if (type.startsWith('audio/')) return Icons.audio_file_outlined;
    if (type.contains('pdf')) return Icons.picture_as_pdf_outlined;
    if (type.contains('text') || type.contains('json') || type.contains('markdown')) {
      return Icons.description_outlined;
    }
    return Icons.insert_drive_file_outlined;
  }

  Future<void> _rename(LibraryItem item) async {
    final TextEditingController controller = TextEditingController(text: item.name);
    final String? name = await showDialog<String>(
      context: context,
      builder: (BuildContext context) => AlertDialog(
        title: const Text('重命名资料'),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(labelText: '资料名称'),
          onSubmitted: (String value) => Navigator.pop(context, value),
        ),
        actions: <Widget>[
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('取消')),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text),
            child: const Text('保存'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (name != null) await widget.state.renameLibraryItem(item, name);
  }

  Future<void> _delete(LibraryItem item) async {
    final bool? confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => AlertDialog(
        icon: const Icon(Icons.delete_outline_rounded),
        title: const Text('删除这份资料？'),
        content: Text('“${item.name}”的文件记录将从你的账户中删除。此操作不可撤销。'),
        actions: <Widget>[
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('取消')),
          FilledButton.tonal(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('确认删除'),
          ),
        ],
      ),
    );
    if (confirmed == true) await widget.state.deleteLibraryItem(item);
  }

  Future<void> _details(LibraryItem item) async {
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (BuildContext context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(22, 6, 22, 28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                children: <Widget>[
                  CircleAvatar(child: Icon(_icon(item.fileType))),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      item.name,
                      style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              _DetailRow(label: '文件类型', value: item.fileType),
              _DetailRow(label: '文件大小', value: _size(item.size)),
              _DetailRow(label: '上传时间', value: _date(item.createdAt)),
              _DetailRow(label: '文件 ID', value: item.id),
              _DetailRow(label: '内容索引', value: item.searchable ? '已可搜索' : '等待或未建立索引'),
              if (item.hash.isNotEmpty) _DetailRow(label: 'SHA-256', value: item.hash),
              const SizedBox(height: 18),
              Row(
                children: <Widget>[
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () {
                        Navigator.pop(context);
                        _rename(item);
                      },
                      icon: const Icon(Icons.edit_outlined),
                      label: const Text('重命名'),
                    ),
                  ),
                  if (item.url.startsWith('http')) ...<Widget>[
                    const SizedBox(width: 10),
                    Expanded(
                      child: FilledButton.tonalIcon(
                        onPressed: () => launchUrl(
                          Uri.parse(item.url),
                          mode: LaunchMode.externalApplication,
                        ),
                        icon: const Icon(Icons.open_in_new_rounded),
                        label: const Text('打开'),
                      ),
                    ),
                  ],
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final List<LibraryItem> items = widget.state.filteredLibraryItems;
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Column(
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 10),
          child: Row(
            children: <Widget>[
              Expanded(
                child: TextField(
                  controller: _search,
                  onChanged: (String value) {
                    widget.state.setLibraryQuery(value);
                    if (_scroll.hasClients) _scroll.jumpTo(0);
                    setState(() => _currentIndex = 0);
                  },
                  decoration: const InputDecoration(
                    hintText: '搜索文件名或类型',
                    prefixIcon: Icon(Icons.search_rounded),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              IconButton.filledTonal(
                tooltip: '刷新资料库',
                onPressed: widget.state.loadingLibrary ? null : widget.state.refreshLibrary,
                icon: widget.state.loadingLibrary
                    ? const SizedBox(
                        width: 19,
                        height: 19,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.refresh_rounded),
              ),
              const SizedBox(width: 8),
              FilledButton.icon(
                onPressed: widget.state.uploading ? null : _pickFiles,
                icon: const Icon(Icons.upload_file_rounded),
                label: const Text('上传'),
              ),
            ],
          ),
        ),
        if (widget.state.uploadProgress.isNotEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 4),
            child: Column(
              children: widget.state.uploadProgress.values
                  .map<Widget>((UploadProgress progress) => Row(
                        children: <Widget>[
                          Expanded(child: Text('${progress.name} · ${progress.stage}')),
                          SizedBox(
                            width: 120,
                            child: LinearProgressIndicator(value: progress.progress),
                          ),
                        ],
                      ))
                  .toList(growable: false),
            ),
          ),
        Expanded(
          child: items.isEmpty
              ? _LibraryEmpty(loading: widget.state.loadingLibrary)
              : Row(
                  children: <Widget>[
                    Expanded(
                      child: ListView.builder(
                        controller: _scroll,
                        itemExtent: _itemExtent,
                        padding: const EdgeInsets.fromLTRB(12, 6, 4, 18),
                        itemCount: items.length,
                        itemBuilder: (BuildContext context, int index) {
                          final LibraryItem item = items[index];
                          return Card(
                            elevation: 0,
                            margin: const EdgeInsets.only(bottom: 6),
                            color: index == _currentIndex
                                ? colors.primaryContainer.withValues(alpha: .28)
                                : null,
                            child: ListTile(
                              leading: Container(
                                width: 44,
                                height: 44,
                                decoration: BoxDecoration(
                                  color: colors.secondaryContainer,
                                  borderRadius: BorderRadius.circular(13),
                                ),
                                child: Icon(_icon(item.fileType), color: colors.onSecondaryContainer),
                              ),
                              title: Text(item.name, maxLines: 1, overflow: TextOverflow.ellipsis),
                              subtitle: Text(
                                '${_date(item.createdAt)} · ${_size(item.size)}',
                                maxLines: 1,
                              ),
                              onTap: () => _details(item),
                              trailing: PopupMenuButton<String>(
                                onSelected: (String value) {
                                  if (value == 'details') _details(item);
                                  if (value == 'rename') _rename(item);
                                  if (value == 'delete') _delete(item);
                                },
                                itemBuilder: (BuildContext context) => const <PopupMenuEntry<String>>[
                                  PopupMenuItem(value: 'details', child: Text('查看详情')),
                                  PopupMenuItem(value: 'rename', child: Text('重命名')),
                                  PopupMenuDivider(),
                                  PopupMenuItem(value: 'delete', child: Text('删除')),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
                    ),
                    _TimelineRail(
                      items: items,
                      index: _currentIndex,
                      onChanged: _jumpTo,
                    ),
                  ],
                ),
        ),
      ],
    );
  }
}

class _TimelineRail extends StatelessWidget {
  const _TimelineRail({
    required this.items,
    required this.index,
    required this.onChanged,
  });

  final List<LibraryItem> items;
  final int index;
  final ValueChanged<int> onChanged;

  String _month(DateTime date) => '${date.year}.${date.month.toString().padLeft(2, '0')}';

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    final int safeIndex = index.clamp(0, items.length - 1);
    return SizedBox(
      width: 68,
      child: Column(
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.only(top: 8, bottom: 6),
            child: Text(
              _month(items[safeIndex].createdAt),
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color: colors.primary,
              ),
            ),
          ),
          Expanded(
            child: LayoutBuilder(
              builder: (BuildContext context, BoxConstraints constraints) {
                final double usable = (constraints.maxHeight - 30).clamp(1, double.infinity);
                final double fraction = items.length <= 1 ? 0 : safeIndex / (items.length - 1);
                void update(double y) {
                  final double value = ((y - 15) / usable).clamp(0, 1);
                  onChanged((value * (items.length - 1)).round());
                }
                return GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTapDown: (TapDownDetails details) => update(details.localPosition.dy),
                  onVerticalDragUpdate: (DragUpdateDetails details) => update(details.localPosition.dy),
                  child: Stack(
                    alignment: Alignment.topCenter,
                    children: <Widget>[
                      Positioned(
                        top: 15,
                        bottom: 15,
                        child: Container(width: 3, color: colors.outlineVariant),
                      ),
                      Positioned(
                        top: 15 + usable * fraction - 8,
                        child: Container(
                          width: 18,
                          height: 18,
                          decoration: BoxDecoration(
                            color: colors.primary,
                            shape: BoxShape.circle,
                            border: Border.all(color: colors.surface, width: 3),
                            boxShadow: const <BoxShadow>[
                              BoxShadow(blurRadius: 6, color: Colors.black26),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text('${safeIndex + 1}/${items.length}', style: const TextStyle(fontSize: 10)),
          ),
        ],
      ),
    );
  }
}

class _LibraryEmpty extends StatelessWidget {
  const _LibraryEmpty({required this.loading});

  final bool loading;

  @override
  Widget build(BuildContext context) => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            if (loading)
              const CircularProgressIndicator()
            else
              Icon(
                Icons.folder_open_rounded,
                size: 62,
                color: Theme.of(context).colorScheme.outline,
              ),
            const SizedBox(height: 14),
            Text(
              loading ? '正在读取资料库…' : '资料库中还没有文件',
              style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
            ),
          ],
        ),
      );
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 7),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            SizedBox(
              width: 86,
              child: Text(label, style: TextStyle(color: Theme.of(context).colorScheme.outline)),
            ),
            Expanded(child: SelectableText(value)),
          ],
        ),
      );
}
