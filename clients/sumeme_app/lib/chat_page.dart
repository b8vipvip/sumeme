import 'dart:io';
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import 'client_api.dart';
import 'client_models.dart';
import 'client_state.dart';
import 'history_search_dialog.dart';

class SuMeMeChatPage extends StatefulWidget {
  const SuMeMeChatPage({super.key, required this.state});

  final SuMeMeClientState state;

  @override
  State<SuMeMeChatPage> createState() => _SuMeMeChatPageState();
}

class _SuMeMeChatPageState extends State<SuMeMeChatPage> {
  final TextEditingController _input = TextEditingController();
  final ScrollController _scroll = ScrollController();
  final FocusNode _focus = FocusNode();
  int _lastMessageCount = 0;
  int _lastAssistantLength = 0;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(_onScroll);
    WidgetsBinding.instance.addPostFrameCallback((_) => _jumpToBottom());
  }

  @override
  void didUpdateWidget(covariant SuMeMeChatPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    final List<ChatMessage> messages = widget.state.displayedMessages;
    final int assistantLength = messages.isEmpty ? 0 : messages.last.text.length;
    if (messages.length != _lastMessageCount || assistantLength != _lastAssistantLength) {
      _lastMessageCount = messages.length;
      _lastAssistantLength = assistantLength;
      if (widget.state.autoScroll && _nearBottom()) {
        WidgetsBinding.instance.addPostFrameCallback((_) => _animateToBottom());
      }
    }
  }

  @override
  void dispose() {
    _input.dispose();
    _scroll
      ..removeListener(_onScroll)
      ..dispose();
    _focus.dispose();
    super.dispose();
  }

  bool _nearBottom() {
    if (!_scroll.hasClients) return true;
    return _scroll.position.maxScrollExtent - _scroll.offset < 220;
  }

  void _onScroll() {
    if (!_scroll.hasClients || _scroll.offset > 72 || !widget.state.canLoadOlder) return;
    final double before = _scroll.position.maxScrollExtent;
    widget.state.loadOlderMessages();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients) return;
      final double delta = _scroll.position.maxScrollExtent - before;
      _scroll.jumpTo((_scroll.offset + delta).clamp(0, _scroll.position.maxScrollExtent));
    });
  }

  void _jumpToBottom() {
    if (_scroll.hasClients) _scroll.jumpTo(_scroll.position.maxScrollExtent);
  }

  void _animateToBottom() {
    if (!_scroll.hasClients) return;
    _scroll.animateTo(
      _scroll.position.maxScrollExtent,
      duration: const Duration(milliseconds: 240),
      curve: Curves.easeOutCubic,
    );
  }

  Future<void> _send() async {
    final String text = _input.text;
    if (text.trim().isEmpty && widget.state.pendingAttachments.isEmpty) return;
    _input.clear();
    await widget.state.sendMessage(text);
    if (mounted) _focus.requestFocus();
  }

  Future<void> _pickFiles({bool imagesOnly = false}) async {
    final FilePickerResult? selection = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      type: imagesOnly ? FileType.image : FileType.any,
      withData: true,
    );
    if (selection == null || selection.files.isEmpty) return;
    final List<UploadFileData> files = <UploadFileData>[];
    for (final PlatformFile file in selection.files) {
      Uint8List? bytes = file.bytes;
      if (bytes == null && file.path != null) bytes = await File(file.path!).readAsBytes();
      if (bytes == null) continue;
      files.add(UploadFileData(
        name: file.name,
        bytes: bytes,
        mimeType: file.mimeType ?? _mime(file.name),
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

  Future<void> _showTools() async {
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      backgroundColor: Theme.of(context).colorScheme.surface,
      builder: (BuildContext context) {
        final ColorScheme colors = Theme.of(context).colorScheme;
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(18, 4, 18, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                const Text(
                  '添加到当前对话',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 4),
                Text(
                  '资料会保存到你的云端资料库，并作为本条消息的附件。',
                  style: TextStyle(color: colors.onSurfaceVariant),
                ),
                const SizedBox(height: 18),
                GridView.count(
                  crossAxisCount: MediaQuery.sizeOf(context).width > 520 ? 4 : 3,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  mainAxisSpacing: 10,
                  crossAxisSpacing: 10,
                  childAspectRatio: 1.25,
                  children: <Widget>[
                    _ToolTile(
                      icon: Icons.upload_file_rounded,
                      label: '上传文件',
                      onTap: () {
                        Navigator.pop(context);
                        _pickFiles();
                      },
                    ),
                    _ToolTile(
                      icon: Icons.image_outlined,
                      label: '上传图片',
                      onTap: () {
                        Navigator.pop(context);
                        _pickFiles(imagesOnly: true);
                      },
                    ),
                    _ToolTile(
                      icon: Icons.manage_search_rounded,
                      label: '查找记忆',
                      onTap: () {
                        Navigator.pop(context);
                        showHistorySearchDialog(this.context, widget.state);
                      },
                    ),
                    _ToolTile(
                      icon: widget.state.memoryEnabled
                          ? Icons.auto_awesome_rounded
                          : Icons.auto_awesome_outlined,
                      label: widget.state.memoryEnabled ? '长期记忆开' : '长期记忆关',
                      onTap: () {
                        widget.state.setMemoryEnabled(!widget.state.memoryEnabled);
                        Navigator.pop(context);
                      },
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    final List<ChatMessage> messages = widget.state.displayedMessages;
    return Column(
      children: <Widget>[
        if (widget.state.hideHistory)
          Container(
            width: double.infinity,
            color: colors.tertiaryContainer.withValues(alpha: .55),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: <Widget>[
                Icon(Icons.visibility_off_outlined, size: 18, color: colors.onTertiaryContainer),
                const SizedBox(width: 7),
                Flexible(
                  child: Text(
                    '已隐藏历史：本次只显示开启后的聊天，发送时也不会携带之前的对话。',
                    style: TextStyle(color: colors.onTertiaryContainer),
                  ),
                ),
              ],
            ),
          ),
        Expanded(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 920),
              child: messages.isEmpty
                  ? _Welcome(state: widget.state, focus: _focus)
                  : ListView.builder(
                      controller: _scroll,
                      padding: const EdgeInsets.fromLTRB(18, 18, 18, 30),
                      itemCount: messages.length + (widget.state.canLoadOlder ? 1 : 0),
                      itemBuilder: (BuildContext context, int index) {
                        if (widget.state.canLoadOlder && index == 0) {
                          return Center(
                            child: Padding(
                              padding: const EdgeInsets.only(bottom: 18),
                              child: TextButton.icon(
                                onPressed: widget.state.loadOlderMessages,
                                icon: const Icon(Icons.history_rounded),
                                label: const Text('载入更早的聊天'),
                              ),
                            ),
                          );
                        }
                        final int messageIndex = index - (widget.state.canLoadOlder ? 1 : 0);
                        final ChatMessage message = messages[messageIndex];
                        final bool showDate = messageIndex == 0 ||
                            !_sameDay(messages[messageIndex - 1].createdAt, message.createdAt);
                        return Column(
                          children: <Widget>[
                            if (showDate) _DateDivider(date: message.createdAt),
                            _MessageRow(message: message),
                          ],
                        );
                      },
                    ),
            ),
          ),
        ),
        if (widget.state.uploadProgress.isNotEmpty)
          Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 920),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 18),
                child: Column(
                  children: widget.state.uploadProgress.values
                      .map((UploadProgress item) => Padding(
                            padding: const EdgeInsets.only(bottom: 6),
                            child: Row(
                              children: <Widget>[
                                const Icon(Icons.cloud_upload_outlined, size: 18),
                                const SizedBox(width: 8),
                                Expanded(child: Text('${item.name} · ${item.stage}')),
                                SizedBox(
                                  width: 90,
                                  child: LinearProgressIndicator(value: item.progress),
                                ),
                              ],
                            ),
                          ))
                      .toList(growable: false),
                ),
              ),
            ),
          ),
        _Composer(
          state: widget.state,
          controller: _input,
          focus: _focus,
          onAdd: _showTools,
          onSend: _send,
        ),
      ],
    );
  }

  bool _sameDay(DateTime a, DateTime b) =>
      a.year == b.year && a.month == b.month && a.day == b.day;
}

class _Welcome extends StatelessWidget {
  const _Welcome({required this.state, required this.focus});

  final SuMeMeClientState state;
  final FocusNode focus;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(28, 54, 28, 30),
      child: Column(
        children: <Widget>[
          Container(
            width: 74,
            height: 74,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: <Color>[colors.primary, colors.tertiary],
              ),
              borderRadius: BorderRadius.circular(26),
              boxShadow: <BoxShadow>[
                BoxShadow(
                  color: colors.primary.withValues(alpha: .2),
                  blurRadius: 28,
                  offset: const Offset(0, 10),
                ),
              ],
            ),
            alignment: Alignment.center,
            child: const Text(
              'Su',
              style: TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.w800),
            ),
          ),
          const SizedBox(height: 22),
          Text(
            state.hideHistory ? '开始一段不带历史的新对话' : '今天想聊点什么？',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w800,
                ),
          ),
          const SizedBox(height: 9),
          Text(
            state.hideHistory
                ? '完整历史仍保存在本机，关闭“隐藏历史”即可恢复显示。'
                : '这是你唯一且持续的对话时间线。重启或重新登录后，历史仍会留在这里。',
            textAlign: TextAlign.center,
            style: TextStyle(color: colors.onSurfaceVariant, height: 1.5),
          ),
          const SizedBox(height: 28),
          Wrap(
            alignment: WrapAlignment.center,
            spacing: 10,
            runSpacing: 10,
            children: <Widget>[
              _Suggestion(icon: Icons.lightbulb_outline_rounded, label: '帮我整理今天的想法', focus: focus),
              _Suggestion(icon: Icons.manage_search_rounded, label: '回忆我们之前聊过的内容', focus: focus),
              _Suggestion(icon: Icons.description_outlined, label: '分析一份资料', focus: focus),
            ],
          ),
        ],
      ),
    );
  }
}

class _Suggestion extends StatelessWidget {
  const _Suggestion({required this.icon, required this.label, required this.focus});

  final IconData icon;
  final String label;
  final FocusNode focus;

  @override
  Widget build(BuildContext context) => ActionChip(
        avatar: Icon(icon, size: 18),
        label: Text(label),
        onPressed: focus.requestFocus,
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 8),
      );
}

class _MessageRow extends StatelessWidget {
  const _MessageRow({required this.message});

  final ChatMessage message;

  String _time(DateTime value) =>
      '${value.hour.toString().padLeft(2, '0')}:${value.minute.toString().padLeft(2, '0')}';

  @override
  Widget build(BuildContext context) {
    final bool user = message.role == 'user';
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Row(
        mainAxisAlignment: user ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          if (!user) ...<Widget>[
            CircleAvatar(
              radius: 17,
              backgroundColor: colors.primaryContainer,
              child: Icon(Icons.auto_awesome_rounded, size: 18, color: colors.primary),
            ),
            const SizedBox(width: 10),
          ],
          Flexible(
            child: Container(
              constraints: const BoxConstraints(maxWidth: 720),
              padding: EdgeInsets.fromLTRB(user ? 16 : 0, 12, user ? 16 : 4, 10),
              decoration: user
                  ? BoxDecoration(
                      color: colors.primaryContainer,
                      borderRadius: const BorderRadius.only(
                        topLeft: Radius.circular(20),
                        topRight: Radius.circular(6),
                        bottomLeft: Radius.circular(20),
                        bottomRight: Radius.circular(20),
                      ),
                    )
                  : null,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  if (message.attachments.isNotEmpty)
                    Wrap(
                      spacing: 7,
                      runSpacing: 7,
                      children: message.attachments
                          .map((ChatAttachment file) => Chip(
                                avatar: const Icon(Icons.insert_drive_file_outlined, size: 17),
                                label: Text(file.name, overflow: TextOverflow.ellipsis),
                                visualDensity: VisualDensity.compact,
                              ))
                          .toList(growable: false),
                    ),
                  if (message.attachments.isNotEmpty && message.text.isNotEmpty)
                    const SizedBox(height: 8),
                  SelectableText(
                    message.text.isEmpty && message.streaming ? '正在思考…' : message.text,
                    style: TextStyle(
                      height: 1.62,
                      fontSize: 15.5,
                      color: user ? colors.onPrimaryContainer : colors.onSurface,
                    ),
                  ),
                  const SizedBox(height: 5),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      Text(
                        _time(message.createdAt),
                        style: TextStyle(fontSize: 11, color: colors.outline),
                      ),
                      if (message.streaming) ...<Widget>[
                        const SizedBox(width: 7),
                        SizedBox(
                          width: 10,
                          height: 10,
                          child: CircularProgressIndicator(
                            strokeWidth: 1.6,
                            color: colors.primary,
                          ),
                        ),
                      ],
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _DateDivider extends StatelessWidget {
  const _DateDivider({required this.date});

  final DateTime date;

  String _label() {
    final DateTime now = DateTime.now();
    if (now.year == date.year && now.month == date.month && now.day == date.day) return '今天';
    final DateTime yesterday = now.subtract(const Duration(days: 1));
    if (yesterday.year == date.year && yesterday.month == date.month && yesterday.day == date.day) {
      return '昨天';
    }
    return '${date.year}年${date.month}月${date.day}日';
  }

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 18),
        child: Row(
          children: <Widget>[
            const Expanded(child: Divider()),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: Text(_label(), style: Theme.of(context).textTheme.bodySmall),
            ),
            const Expanded(child: Divider()),
          ],
        ),
      );
}

class _Composer extends StatelessWidget {
  const _Composer({
    required this.state,
    required this.controller,
    required this.focus,
    required this.onAdd,
    required this.onSend,
  });

  final SuMeMeClientState state;
  final TextEditingController controller;
  final FocusNode focus;
  final VoidCallback onAdd;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Material(
      color: Theme.of(context).scaffoldBackgroundColor,
      child: SafeArea(
        top: false,
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 920),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(14, 8, 14, 14),
              child: Container(
                decoration: BoxDecoration(
                  color: colors.surface,
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: colors.outlineVariant),
                  boxShadow: <BoxShadow>[
                    BoxShadow(
                      color: Colors.black.withValues(alpha: .06),
                      blurRadius: 20,
                      offset: const Offset(0, 7),
                    ),
                  ],
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    if (state.pendingAttachments.isNotEmpty)
                      SizedBox(
                        height: 52,
                        child: ListView.separated(
                          padding: const EdgeInsets.fromLTRB(12, 9, 12, 2),
                          scrollDirection: Axis.horizontal,
                          itemBuilder: (BuildContext context, int index) {
                            final ChatAttachment file = state.pendingAttachments[index];
                            return InputChip(
                              avatar: const Icon(Icons.description_outlined, size: 17),
                              label: Text(file.name, overflow: TextOverflow.ellipsis),
                              onDeleted: () => state.removePendingAttachment(file.id),
                            );
                          },
                          separatorBuilder: (_, __) => const SizedBox(width: 6),
                          itemCount: state.pendingAttachments.length,
                        ),
                      ),
                    TextField(
                      controller: controller,
                      focusNode: focus,
                      minLines: 1,
                      maxLines: 7,
                      textInputAction: TextInputAction.newline,
                      keyboardType: TextInputType.multiline,
                      decoration: const InputDecoration(
                        hintText: '给 SuMeMe 发消息…',
                        border: InputBorder.none,
                        enabledBorder: InputBorder.none,
                        focusedBorder: InputBorder.none,
                        contentPadding: EdgeInsets.fromLTRB(18, 15, 18, 8),
                      ),
                      onSubmitted: (String value) {
                        if (!HardwareKeyboard.instance.isShiftPressed) onSend();
                      },
                    ),
                    Padding(
                      padding: const EdgeInsets.fromLTRB(8, 0, 8, 8),
                      child: Row(
                        children: <Widget>[
                          IconButton.filledTonal(
                            onPressed: state.uploading ? null : onAdd,
                            tooltip: '添加文件和工具',
                            icon: state.uploading
                                ? const SizedBox(
                                    width: 18,
                                    height: 18,
                                    child: CircularProgressIndicator(strokeWidth: 2),
                                  )
                                : const Icon(Icons.add_rounded),
                          ),
                          const SizedBox(width: 6),
                          PopupMenuButton<String>(
                            enabled: state.models.isNotEmpty,
                            tooltip: '选择模型',
                            onSelected: state.selectModel,
                            itemBuilder: (BuildContext context) => state.models
                                .map((String model) => PopupMenuItem<String>(
                                      value: model,
                                      child: Text(model),
                                    ))
                                .toList(growable: false),
                            child: Chip(
                              avatar: const Icon(Icons.tune_rounded, size: 16),
                              label: ConstrainedBox(
                                constraints: const BoxConstraints(maxWidth: 170),
                                child: Text(
                                  state.selectedModel.isEmpty ? '未配置模型' : state.selectedModel,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              visualDensity: VisualDensity.compact,
                            ),
                          ),
                          const SizedBox(width: 6),
                          Tooltip(
                            message: state.memoryEnabled ? '长期记忆已开启' : '长期记忆已关闭',
                            child: IconButton(
                              onPressed: () => state.setMemoryEnabled(!state.memoryEnabled),
                              icon: Icon(
                                state.memoryEnabled
                                    ? Icons.auto_awesome_rounded
                                    : Icons.auto_awesome_outlined,
                                color: state.memoryEnabled ? colors.primary : colors.outline,
                              ),
                            ),
                          ),
                          const Spacer(),
                          IconButton.filled(
                            onPressed: state.sending ? null : onSend,
                            tooltip: '发送',
                            icon: state.sending
                                ? const SizedBox(
                                    width: 18,
                                    height: 18,
                                    child: CircularProgressIndicator(strokeWidth: 2),
                                  )
                                : const Icon(Icons.arrow_upward_rounded),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _ToolTile extends StatelessWidget {
  const _ToolTile({required this.icon, required this.label, required this.onTap});

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(18),
        child: Ink(
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(18),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: <Widget>[
              Icon(icon, size: 27),
              const SizedBox(height: 8),
              Text(label, style: const TextStyle(fontWeight: FontWeight.w600)),
            ],
          ),
        ),
      );
}
