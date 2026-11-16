-- NoiseAI DB 스키마 (PostgreSQL). scripts/export_docs.py 로 생성됨 — 직접 고치지 말고 models.py 를 고칠 것

CREATE TABLE users (
	id SERIAL NOT NULL,
	email VARCHAR(255) NOT NULL,
	password_hash VARCHAR(255) NOT NULL,
	store_name VARCHAR(100),
	gender VARCHAR(20),
	age_group VARCHAR(20),
	category VARCHAR(30),
	mood VARCHAR(30),
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	noise_strategy VARCHAR(10) DEFAULT 'stable' NOT NULL,
	total_seats INTEGER DEFAULT 0 NOT NULL,
	public_id VARCHAR(16),
	guest_keywords TEXT,
	guest_keywords_until TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE INDEX ix_users_public_id ON users (public_id);

CREATE TABLE feedback (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	mode VARCHAR(10) NOT NULL,
	keywords TEXT,
	track_id INTEGER,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_feedback_user_time ON feedback (user_id, created_at);

CREATE TABLE sales_hourly (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	hour_bucket VARCHAR(13) NOT NULL,
	sales_amount INTEGER NOT NULL,
	order_count INTEGER NOT NULL,
	source VARCHAR(10) NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_sales_user_hour UNIQUE (user_id, hour_bucket),
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE seat_events (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	seat_id VARCHAR(30) NOT NULL,
	event VARCHAR(10) NOT NULL,
	party_size INTEGER,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_seat_events_user_time ON seat_events (user_id, created_at);

CREATE TABLE status_log (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	noise_db FLOAT NOT NULL,
	hour_bucket VARCHAR(13) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	zone_id VARCHAR(30),
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_status_log_created_at ON status_log (created_at);

CREATE INDEX ix_status_log_user_hour ON status_log (user_id, hour_bucket);

CREATE TABLE tracks (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	prompt TEXT NOT NULL,
	audio_url VARCHAR(1000),
	is_played BOOLEAN NOT NULL,
	status VARCHAR(20) NOT NULL,
	error TEXT,
	prediction_id VARCHAR(64),
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	completed_at TIMESTAMP WITH TIME ZONE,
	source VARCHAR(10) DEFAULT 'auto' NOT NULL,
	priority INTEGER DEFAULT 0 NOT NULL,
	is_skipped BOOLEAN DEFAULT false NOT NULL,
	noise_level VARCHAR(10),
	situation VARCHAR(20),
	feedback_id INTEGER,
	played_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_tracks_status ON tracks (status);

CREATE INDEX ix_tracks_user_id ON tracks (user_id);
