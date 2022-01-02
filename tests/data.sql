-- >>> from werkzeug.security import generate_password_hash
-- >>> generate_password_hash('pw1')
-- 'pbkdf2:sha256:260000$L4S8nE46PRuhLqMK$820155e46f6f68643d668d7bc6f4c6e1db7c02505275e40a44b8e8fe8c640985'
-- >>> generate_password_hash('pw2')
-- 'pbkdf2:sha256:260000$zo4Su1dUaG23vfVr$fc34ea59029c6b1b7e19a48b86aceb862460529ab8c2fde586735261a1028640'

INSERT INTO user (username, password)
VALUES
    ('test', 'pbkdf2:sha256:50000$TCI4GzcX$0de171a4f4dac32e3364c7ddc7c14f3e2fa61f2d17574483f7ffbb431b4acb2f'),
    ('other', 'pbkdf2:sha256:260000$zo4Su1dUaG23vfVr$fc34ea59029c6b1b7e19a48b86aceb862460529ab8c2fde586735261a1028640');

INSERT INTO post (title, body, author_id, created)
VALUES
  ('test title', 'test' || x'0a' || 'body', 1, '2018-01-01 00:00:00'),
  ('test2', 'test2' || x'0a' || 'body2', 2, '2019-01-01 00:00:00');
