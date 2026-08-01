import 'package:flutter/material.dart';

import 'client_state.dart';

class SuMeMeAuthPage extends StatefulWidget {
  const SuMeMeAuthPage({super.key, required this.state});

  final SuMeMeClientState state;

  @override
  State<SuMeMeAuthPage> createState() => _SuMeMeAuthPageState();
}

class _SuMeMeAuthPageState extends State<SuMeMeAuthPage> {
  final TextEditingController _name = TextEditingController();
  final TextEditingController _email = TextEditingController();
  final TextEditingController _password = TextEditingController();
  bool _signup = false;
  bool _obscure = true;

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final String email = _email.text.trim();
    final String password = _password.text;
    if (email.isEmpty || password.length < 8) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请输入有效邮箱和至少 8 位密码')),
      );
      return;
    }
    if (_signup) {
      await widget.state.signUp(
        _name.text.trim().isEmpty ? email.split('@').first : _name.text.trim(),
        email,
        password,
      );
    } else {
      await widget.state.signIn(email, password);
    }
  }

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: <Color>[
              colors.primaryContainer.withValues(alpha: .42),
              Theme.of(context).scaffoldBackgroundColor,
              colors.secondaryContainer.withValues(alpha: .25),
            ],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 440),
                child: Card(
                  elevation: 0,
                  color: colors.surface.withValues(alpha: .94),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(28),
                    side: BorderSide(color: colors.outlineVariant),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(30, 34, 30, 28),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: <Widget>[
                        Align(
                          child: Container(
                            width: 66,
                            height: 66,
                            decoration: BoxDecoration(
                              color: colors.primary,
                              borderRadius: BorderRadius.circular(22),
                            ),
                            alignment: Alignment.center,
                            child: Text(
                              'Su',
                              style: TextStyle(
                                color: colors.onPrimary,
                                fontSize: 25,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(height: 22),
                        Text(
                          _signup ? '创建 SuMeMe 账户' : '欢迎回到 SuMeMe',
                          textAlign: TextAlign.center,
                          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                                fontWeight: FontWeight.w800,
                              ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          _signup
                              ? '创建账户后，你的对话、记忆与资料将按账户隔离。'
                              : '登录后继续你的唯一对话时间线。',
                          textAlign: TextAlign.center,
                          style: TextStyle(color: colors.onSurfaceVariant),
                        ),
                        const SizedBox(height: 26),
                        if (_signup) ...<Widget>[
                          TextField(
                            controller: _name,
                            textInputAction: TextInputAction.next,
                            decoration: const InputDecoration(
                              labelText: '昵称',
                              prefixIcon: Icon(Icons.person_outline_rounded),
                            ),
                          ),
                          const SizedBox(height: 14),
                        ],
                        TextField(
                          controller: _email,
                          keyboardType: TextInputType.emailAddress,
                          textInputAction: TextInputAction.next,
                          autofillHints: const <String>[AutofillHints.email],
                          decoration: const InputDecoration(
                            labelText: '邮箱',
                            prefixIcon: Icon(Icons.mail_outline_rounded),
                          ),
                        ),
                        const SizedBox(height: 14),
                        TextField(
                          controller: _password,
                          obscureText: _obscure,
                          textInputAction: TextInputAction.done,
                          onSubmitted: (_) => _submit(),
                          autofillHints: <String>[
                            _signup
                                ? AutofillHints.newPassword
                                : AutofillHints.password,
                          ],
                          decoration: InputDecoration(
                            labelText: '密码',
                            prefixIcon: const Icon(Icons.lock_outline_rounded),
                            suffixIcon: IconButton(
                              onPressed: () => setState(() => _obscure = !_obscure),
                              icon: Icon(
                                _obscure
                                    ? Icons.visibility_outlined
                                    : Icons.visibility_off_outlined,
                              ),
                            ),
                          ),
                        ),
                        if (widget.state.errorMessage != null) ...<Widget>[
                          const SizedBox(height: 14),
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: colors.errorContainer,
                              borderRadius: BorderRadius.circular(14),
                            ),
                            child: Text(
                              widget.state.errorMessage!,
                              style: TextStyle(color: colors.onErrorContainer),
                            ),
                          ),
                        ],
                        const SizedBox(height: 20),
                        FilledButton(
                          onPressed: widget.state.authenticating ? null : _submit,
                          style: FilledButton.styleFrom(
                            minimumSize: const Size.fromHeight(52),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                          ),
                          child: widget.state.authenticating
                              ? const SizedBox(
                                  width: 22,
                                  height: 22,
                                  child: CircularProgressIndicator(strokeWidth: 2),
                                )
                              : Text(_signup ? '创建并登录' : '登录'),
                        ),
                        const SizedBox(height: 12),
                        TextButton(
                          onPressed: widget.state.registrationEnabled
                              ? () => setState(() => _signup = !_signup)
                              : null,
                          child: Text(
                            _signup
                                ? '已有账户？返回登录'
                                : widget.state.registrationEnabled
                                    ? '没有账户？创建账户'
                                    : '管理员已关闭公开注册',
                          ),
                        ),
                        const SizedBox(height: 8),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: <Widget>[
                            Icon(
                              widget.state.isConnected
                                  ? Icons.cloud_done_outlined
                                  : Icons.cloud_off_outlined,
                              size: 16,
                              color: widget.state.isConnected
                                  ? colors.primary
                                  : colors.error,
                            ),
                            const SizedBox(width: 6),
                            Text(
                              widget.state.isConnected ? '服务已连接' : '服务连接异常',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
