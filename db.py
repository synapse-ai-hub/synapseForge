import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
import pandas as pd
from sqlalchemy import create_engine
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
import time
import sys
from typing import Optional, Dict, List, Union

# Configuración de paths 
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

class EmptyQuery(Exception):
    pass

class UserIDException(Exception):
    pass

class PermissionDeniedException(Exception):
    pass


class DB:
    def __init__(self, chroma_path: str = f'{project_root}/intelligence/rag_system/chroma_db/'):
        load_dotenv()
        self.chroma_path = chroma_path
        self.init_sql()  
        self.init_chroma()

    def init_sql(self) -> None:
        self.host = os.getenv('POSTGRES_HOST', 'localhost')
        self.port = int(os.getenv('POSTGRES_PORT', 5432))
        self.user = os.getenv('POSTGRES_USER')
        self.password = os.getenv('POSTGRES_PASSWORD')
        self.database = os.getenv('POSTGRES_DATABASE')

        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                cursor_factory=RealDictCursor
            )
            self.conn.autocommit = True
            self.sql = self.conn.cursor()
            # print("Conexión a PostgreSQL establecida correctamente.")
            
            # SQLAlchemy engine para pandas (manteniendo compatibilidad)
            uri = f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
            self.engine = create_engine(uri)
            
        except Exception as e:
            print(f'Error al conectar a PostgreSQL: {str(e)}')

    def init_chroma(self) -> None:
        """Mantiene la misma funcionalidad de ChromaDB"""
        chroma_ = chromadb.PersistentClient(self.chroma_path)
        
        self.embed_func = SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2",
            device="cpu"
        )
        
        collections = ['prospect', 'strategy', 'owner', 'prompt', 'outreach', 
                      'chat', 'temp', 'system_template', 'user_template', 'data_analysis', 'search']
        
        self.chroma = {}
        for collection_name in collections:
            self.chroma[collection_name] = chroma_.get_or_create_collection(
                name=collection_name,
                embedding_function=self.embed_func,
                configuration={"hnsw": {"space": "cosine", "ef_construction": 200}}
            )

    def create_db_sql(self) -> None:
        """Crea la base de datos si no existe (PostgreSQL)"""
        try:
            # Conectar a postgres database para crear la nueva
            temp_conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database='postgres'
            )
            temp_conn.autocommit = True
            temp_cursor = temp_conn.cursor()
            
            temp_cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", 
                (self.database,)
            )
            
            if not temp_cursor.fetchone():
                temp_cursor.execute(f'CREATE DATABASE "{self.database}"')
                print(f'Base de datos {self.database} creada automáticamente.')
            else:
                print(f'Base de datos {self.database} ya existe.')
            
            temp_cursor.close()
            temp_conn.close()
            
        except Exception as e:
            print(f'Error al crear la base de datos: {e}')

    def create_tables_sql(self) -> None:
        """Crea todas las tablas adaptadas a PostgreSQL con soporte multi-tenant"""
        try:
            # Tabla users (nueva)
            self.sql.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    email VARCHAR(255) UNIQUE NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    google_id VARCHAR(100) UNIQUE,
                    google_access_token TEXT,
                    google_refresh_token TEXT,
                    role VARCHAR(20),
                    subscription_status VARCHAR(20) DEFAULT 'starter' 
                        CHECK (subscription_status IN ('starter', 'growth', 'scale', 'owner', 'invited')),
                    subscription_expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT true
                );
            """)

            # Índices para users
            self.sql.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
            self.sql.execute("CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);")
            self.sql.execute("CREATE INDEX IF NOT EXISTS idx_users_subscription ON users(subscription_status, subscription_expires_at);")

            self.sql.execute("""
                CREATE TABLE IF NOT EXISTS user_log (
                    id SERIAL PRIMARY KEY,
                    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                    action VARCHAR(255) NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            #Index
            self.sql.execute("CREATE INDEX IF NOT EXISTS idx_user_log_user_id ON user_log(user_id);")

            # Prospects
            self.sql.execute("""
                CREATE TABLE IF NOT EXISTS prospect (
                    id SERIAL PRIMARY KEY,
                    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                    nombre VARCHAR(255),
                    empresa VARCHAR(100),
                    cargo VARCHAR(100),
                    puntuacion FLOAT,                    
                    grado_de_contacto VARCHAR(50),
                    linkedin VARCHAR(500),
                    bool_search VARCHAR(255),
                    fecha DATE,
                    ubicacion VARCHAR(100)
                );
            """)
            self.sql.execute("CREATE INDEX IF NOT EXISTS idx_prospect_user_id ON prospect(user_id);")

            # Priority 1
            self.sql.execute("""
                CREATE TABLE IF NOT EXISTS priority_1 (
                    id SERIAL PRIMARY KEY,
                    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                    nombre VARCHAR(255),
                    empresa VARCHAR(100),
                    cargo VARCHAR(100),
                    puntuacion FLOAT,                    
                    grado_de_contacto VARCHAR(50),
                    linkedin VARCHAR(500),
                    bool_search VARCHAR(255),
                    fecha DATE
                );
            """)
            self.sql.execute("CREATE INDEX IF NOT EXISTS idx_priority_1_user_id ON priority_1(user_id);")

            # Priority 2
            self.sql.execute("""
                CREATE TABLE IF NOT EXISTS priority_2 (
                    id SERIAL PRIMARY KEY,
                    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                    nombre VARCHAR(255),
                    empresa VARCHAR(100),
                    cargo VARCHAR(100),
                    puntuacion FLOAT,                    
                    grado_de_contacto VARCHAR(50),
                    linkedin VARCHAR(500),
                    bool_search VARCHAR(255),
                    fecha DATE
                );
            """)
            self.sql.execute("CREATE INDEX IF NOT EXISTS idx_priority_2_user_id ON priority_2(user_id);")

            # Discarded
            self.sql.execute("""
                CREATE TABLE IF NOT EXISTS discarded (
                    id SERIAL PRIMARY KEY,
                    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                    nombre VARCHAR(255),
                    empresa VARCHAR(100),
                    cargo VARCHAR(100),
                    puntuacion FLOAT,                    
                    grado_de_contacto VARCHAR(50),
                    linkedin VARCHAR(500),
                    bool_search VARCHAR(255),
                    fecha DATE
                );
            """)
            self.sql.execute("CREATE INDEX IF NOT EXISTS idx_discarded_user_id ON discarded(user_id);")

            # Outreach
            self.sql.execute("""
                CREATE TABLE IF NOT EXISTS outreach (
                    id SERIAL PRIMARY KEY,
                    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                    puntuacion FLOAT,
                    nombre VARCHAR(255),
                    mensaje_1 VARCHAR(20),
                    respuesta_1 VARCHAR(20),
                    mensaje_2 VARCHAR(20),
                    respuesta_2 VARCHAR(20),
                    reunion VARCHAR(20),         
                    fecha DATE
                );
            """)
            self.sql.execute("CREATE INDEX IF NOT EXISTS idx_outreach_user_id ON outreach(user_id);")

            # # Collector
            # self.sql.execute("""
            #     CREATE TABLE IF NOT EXISTS collector (
            #         id SERIAL PRIMARY KEY,
            #         user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            #         url VARCHAR(500),
            #         fecha DATE,
            #         bool_search VARCHAR(255)
            #     );
            # """)
            # self.sql.execute("CREATE INDEX IF NOT EXISTS idx_collector_user_id ON collector(user_id);")

            # Bool search
            self.sql.execute("""
                CREATE TABLE IF NOT EXISTS bool_search (
                    conversation_id VARCHAR(255),
                    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                    bool_search VARCHAR(255)
                );
            """)
            self.sql.execute("CREATE INDEX IF NOT EXISTS idx_bool_search_conversation_id ON bool_search(conversation_id);")

            # Strategy
            self.sql.execute("""
                CREATE TABLE IF NOT EXISTS strategy (
                    id SERIAL PRIMARY KEY,
                    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                    fecha DATE
                );
            """)
            self.sql.execute("CREATE INDEX IF NOT EXISTS idx_strategy_user_id ON strategy(user_id);")



            # Strategy
            self.sql.execute("""
                CREATE TABLE IF NOT EXISTS out_of_query (
                    
                    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                    url VARCHAR(100),
                    bool_search VARCHAR(255)
                );
            """)
            self.sql.execute("""CREATE INDEX IF NOT EXISTS idx_out_of_query_user_query_url
                                ON out_of_query (user_id, bool_search, url);
                            """)

            # Log (adaptado para multi-tenant)
            self.sql.execute("""
                CREATE TABLE IF NOT EXISTS log (
                    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                    task_id SERIAL PRIMARY KEY,
                    task_name VARCHAR(30),
                    status VARCHAR(10),
                    start_task VARCHAR(50),
                    end_task VARCHAR(50),
                    duration_sec FLOAT,
                    input_tokens INTEGER,
                    output_tokens INTEGER
                );
            """)
            self.sql.execute("CREATE INDEX IF NOT EXISTS idx_log_user_id ON log(user_id);")

            print("Tablas de PostgreSQL creadas/verificadas correctamente.")

        except Exception as e:
            print(f'Error al crear las tablas: {e}')

    # ===== MÉTODOS PARA MANEJO DE USUARIOS =====
    
    def add_user(self, email: str, name: str, role: str, google_id: str = None, 
                 subscription_status: str = 'starter') -> str:
        """Agrega un nuevo usuario y devuelve su UUID"""
        try:
            self.sql.execute("""
                INSERT INTO users (email, name, google_id, role, subscription_status)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (email, name, google_id, role, subscription_status))
            
            result = self.sql.fetchone()
            user_id = str(result['id'])
            print(f"Usuario {email} agregado con ID: {user_id}")
            return user_id
            
        except Exception as e:
            print(f"Error al agregar usuario: {str(e)}")
            return None

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Obtiene un usuario por email"""
        try:
            self.sql.execute("SELECT * FROM users WHERE email = %s", (email,))
            result = self.sql.fetchone()
            return dict(result) if result else None
        except Exception as e:
            print(f"Error al obtener usuario: {str(e)}")
            return None

    def get_user_by_google_id(self, google_id: str) -> Optional[Dict]:
        """Obtiene un usuario por Google ID"""
        try:
            self.sql.execute("SELECT * FROM users WHERE google_id = %s", (google_id,))
            result = self.sql.fetchone()
            return dict(result) if result else None
        except Exception as e:
            print(f"Error al obtener usuario por Google ID: {str(e)}")
            return None

    def update_user_subscription(self, user_id: str, status: str, 
                               expires_at: str = None) -> bool:
        """Actualiza la suscripción de un usuario"""
        try:
            self.sql.execute("""
                UPDATE users 
                SET subscription_status = %s, 
                    subscription_expires_at = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (status, expires_at, user_id))
            
            return self.sql.rowcount > 0
        except Exception as e:
            print(f"Error al actualizar suscripción: {str(e)}")
            return False
    
    def update_user_google_tokens(self, user_id: str, access_token: str, refresh_token: str = None) -> bool:
        """Actualiza los tokens de Google para un usuario"""
        try:
            if refresh_token:
                self.sql.execute("""
                    UPDATE users 
                    SET google_access_token = %s, google_refresh_token = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (access_token, refresh_token, user_id))
            else:
                self.sql.execute("""
                    UPDATE users 
                    SET google_access_token = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (access_token, user_id))
            
            # COMMIT CRUCIAL
            self.conn.commit()
            
            return self.sql.rowcount > 0
        except Exception as e:
            print(f"Error al actualizar tokens de Google: {str(e)}")
            self.conn.rollback()
            return False
    
    def get_user_google_token(self, user_id: str) -> Optional[str]:
        """Obtiene el access token de Google para un usuario"""
        try:
            self.sql.execute("""
                SELECT google_access_token FROM users WHERE id = %s
            """, (user_id,))
            
            result = self.sql.fetchone()
            if result:
                token = result['google_access_token']
                if token and token != '0' and token != 0:
                    return token
            return None
        except Exception as e:
            print(f"Error al obtener token de Google: {str(e)}")
            return None
    
    def get_user_google_refresh_token(self, user_id: str) -> Optional[str]:
        """Obtiene el refresh token de Google para un usuario"""
        try:
            self.sql.execute("""
                SELECT google_refresh_token FROM users WHERE id = %s
            """, (user_id,))
            
            result = self.sql.fetchone()
            if result:
                token = result['google_refresh_token']  # Usar clave en lugar de índice
                if token and token != '0' and token != 0:
                    return token
            return None
        except Exception as e:
            print(f"Error al obtener refresh token de Google: {str(e)}")
            return None

    # ===== MÉTODOS ADAPTADOS PARA MULTI-TENANT =====

    def add_sql(self, table: str, values: Union[Dict, List[Dict]], 
                user_id: str = None) -> None:
        """Versión adaptada para PostgreSQL con soporte opcional de user_id"""
        try:
            values_list = [values] if isinstance(values, dict) else values
            if not values_list:
                print(f"No se proporcionaron valores para insertar en {table}.")
                return
            
            # Agregar user_id automáticamente si se proporciona
            if user_id and table != 'users':  # No agregar user_id a la tabla users
                for value in values_list:
                    value['user_id'] = user_id
            
            cols = list(values_list[0].keys())
            
            # Filtrar duplicados (manteniendo lógica existente)
            values_to_insert = []
            for value in values_list:
                if table == 'collector':
                    where_clause = "url = %s"
                    params = (value['url'],)
                    if user_id:
                        where_clause += " AND user_id = %s"
                        params = (value['url'], user_id)
                    
                    self.sql.execute(f"SELECT url FROM collector WHERE {where_clause}", params)
                    if self.sql.fetchone():
                        print(f'{value["url"]} ya existe en {table}. No se insertará.')
                        continue
                elif 'nombre' in value:
                    where_clause = "nombre = %s"
                    params = (value['nombre'],)
                    if user_id:
                        where_clause += " AND user_id = %s"
                        params = (value['nombre'], user_id)
                    
                    self.sql.execute(f"SELECT nombre FROM {table} WHERE {where_clause}", params)
                    if self.sql.fetchone():
                        print(f'{value["nombre"]} ya existe en {table}. No se insertará.')
                        continue
                
                values_to_insert.append(value)
            
            # Insertar valores válidos
            if values_to_insert:
                # Adaptar formato de fecha para PostgreSQL
                placeholders = []
                for col in cols:
                    if col == 'fecha':
                        placeholders.append("TO_DATE(%s, 'DD/MM/YY')")
                    else:
                        placeholders.append('%s')
                
                placeholders_str = ', '.join(placeholders)
                sql_insert = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders_str})"
                
                for value in values_to_insert:
                    self.sql.execute(sql_insert, tuple(value.values()))
                
                print(f"Registros insertados en PostgreSQL. Tabla: {table}")
            else:
                print(f"No hay registros nuevos para insertar en {table}.")
                
        except Exception as e:
            print(f"Error al insertar en PostgreSQL: {str(e)}")

    def query_sql(self, table: str, columns: str = "*", where: str = None, 
                  group_by: str = None, order_by: str = None, desc: bool = True, 
                  limit: int = None, params: tuple = None, user_id: str = None) -> List[Dict]:
        """Versión adaptada para PostgreSQL con filtro opcional por user_id"""
        try:
            sql_query = f"SELECT {columns} FROM {table}"
            
            where_conditions = []
            query_params = []
            
            # Agregar filtro por user_id automáticamente si se proporciona y la tabla lo soporta
            if user_id and table not in ['users']:
                # Verificar si la tabla tiene columna user_id
                self.sql.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = %s AND column_name = 'user_id'
                """, (table,))
                
                if self.sql.fetchone():
                    where_conditions.append("user_id = %s")
                    query_params.append(user_id)
            
            # Agregar condiciones WHERE adicionales
            if where:
                where_conditions.append(where)
                if params:
                    query_params.extend(params)
            
            # Construir cláusula WHERE
            if where_conditions:
                sql_query += f" WHERE {' AND '.join(where_conditions)}"
            
            if group_by:
                sql_query += f' GROUP BY {group_by}'
            if order_by:
                sql_query += f" ORDER BY {order_by}"
                if desc:
                    sql_query += " DESC"
            if limit:
                sql_query += f" LIMIT {limit}"
            
            self.sql.execute(sql_query, tuple(query_params))
            results = self.sql.fetchall()
            
            # Convertir RealDictRow a dict normal
            return [dict(row) for row in results]

        except Exception as e:
            print(f'Error en consulta PostgreSQL: {str(e)}')
            return []

    def delete_sql(self, table: str, where: str, params: Union[str, List], 
                   user_id: str = None) -> None:
        """Versión adaptada para PostgreSQL con filtro opcional por user_id"""
        try:
            where_conditions = []
            query_params = []
            
            # Agregar filtro por user_id si se proporciona
            if user_id and table not in ['users']:
                where_conditions.append("user_id = %s")
                query_params.append(user_id)
            
            # Procesar parámetros de WHERE
            if isinstance(params, (list, tuple)):
                if len(params) == 0:
                    print(f'No se proporcionaron parámetros para borrar en {table}.')
                    return
                if '%s' not in where:  
                    placeholders = ', '.join(['%s'] * len(params))
                    where = f'{where} IN ({placeholders})'
                query_params.extend(params)
            else:
                query_params.append(params)
            
            where_conditions.append(where)
            
            sql_delete = f'DELETE FROM {table} WHERE {" AND ".join(where_conditions)}'
            self.sql.execute(sql_delete, tuple(query_params))

            print(f'Registro(s) eliminado(s) en PostgreSQL. Tabla: {table}, Filas afectadas: {self.sql.rowcount}')

        except Exception as e:
            print(f'Error al borrar en PostgreSQL: {str(e)}')

    def update_sql(self, table: str, values: Dict, where: str, params: tuple, 
                   user_id: str = None) -> None:
        """Versión adaptada para PostgreSQL con filtro opcional por user_id"""
        try:
            where_conditions = []
            query_params = list(values.values())
            
            # Agregar filtro por user_id si se proporciona
            if user_id and table not in ['users']:
                where_conditions.append("user_id = %s")
                query_params.append(user_id)
            
            where_conditions.append(where)
            query_params.extend(params)
            
            set_clause = ', '.join([f"{k} = %s" for k in values.keys()])
            sql_update = f"UPDATE {table} SET {set_clause} WHERE {' AND '.join(where_conditions)}"
            
            self.sql.execute(sql_update, tuple(query_params))
            print(f'Registro(s) actualizado(s) en PostgreSQL. Tabla: {table}, Filas afectadas: {self.sql.rowcount}')

        except Exception as e:
            print(f'Error al actualizar PostgreSQL: {str(e)}')

    # ===== MÉTODOS PARA CHROMADB CON SOPORTE MULTI-TENANT =====

    def add_chroma(self, collection_name: str, ids: List[str], elements: List[str], metadatas: List[Dict], user_id: str, role: str):  
        """Agrega documentos a ChromaDB con user_id en metadatos"""
        try:
            # Determinar si la colección requiere filtrado por usuario
            user_filtered_collections = ['owner', 'user_template', 'prospect', 
                                       'outreach', 'chat', 'temp', 'user_template', 'data_analysis', 'search']
            
            if collection_name in user_filtered_collections and user_id is None:
                raise UserIDException(f'Debe proporcionar user_id para la colección {collection_name}')
            
            if role != 'owner' and collection_name not in user_filtered_collections:
                raise PermissionDeniedException(f'Solo usuarios con permiso pueden agregar archivos en la colección {collection_name}')
            
                     
            self.chroma[collection_name].add(ids=ids, documents=elements, metadatas=metadatas)
            
            filter_msg = "con filtrado por usuario" if collection_name in user_filtered_collections else "sin filtrado"
            print(f"Documentos agregados a ChromaDB '{collection_name}' {filter_msg}")
            
        except Exception as e:
            print(f"Error al agregar a ChromaDB: {str(e)}")



    def update_chroma(self, collection_name: str, ids: List[str], user_id: str, role: str, elements: List[str] = None, metadatas: List[Dict] = None):  
        """Actualiza documentos de ChromaDB con user_id en metadatos"""
        try:
            # Determinar si la colección requiere filtrado por usuario
           
            user_filtered_collections = ['owner', 'user_template', 'prospect', 
                                       'outreach', 'chat', 'temp', 'user_template', 'data_analysis', 'search']

            if collection_name in user_filtered_collections and user_id is None:
                raise UserIDException(f'Debe proporcionar user_id para la colección {collection_name}')
            
            if role != 'owner' and collection_name not in user_filtered_collections:
                raise PermissionDeniedException(f'Solo usuarios con permiso pueden actualizar archivos en la colección {collection_name}')
            
            archivo = self.chroma[collection_name].get(ids=ids, where={"user_id": user_id}, include=['metadatas', 'documents'])

            if not metadatas:
                metadatas = archivo['metadatas']
            if not elements:
                elements = archivo['documents']
                     
            self.chroma[collection_name].update(ids=ids, documents=elements, metadatas=metadatas)
            
            filter_msg = "con filtrado por usuario" if collection_name in user_filtered_collections else "sin filtrado"
            print(f"Documentos actualizados en ChromaDB '{collection_name}' {filter_msg}")
            
        except Exception as e:
            print(f"Error al actualizar en ChromaDB: {str(e)}")



    def delete_chroma(self, collection_name: str, ids: List[str], user_id: str, role: str):  
        """Borra documentos de ChromaDB con user_id en metadatos"""
        try:
            # Determinar si la colección requiere filtrado por usuario
            user_filtered_collections = ['owner', 'user_template', 'prospect', 
                                       'outreach', 'chat', 'temp', 'user_template', 'data_analysis', 'search']
            
            if collection_name in user_filtered_collections and user_id is None:
                raise UserIDException(f'Debe proporcionar user_id para la colección {collection_name}')
            
            if role != 'owner' and collection_name not in user_filtered_collections:
                raise PermissionDeniedException(f'Solo usuarios con permiso pueden borrar archivos en la colección {collection_name}')
                                 
            self.chroma[collection_name].delete(ids=ids)
            
            filter_msg = "con filtrado por usuario" if collection_name in user_filtered_collections else "sin filtrado"
            print(f"Documentos borrados de ChromaDB '{collection_name}' {filter_msg}")
            
        except Exception as e:
            print(f"Error al borrar en ChromaDB: {str(e)}")
            

    
    # ===== MÉTODOS LEGACY MANTENIDOS PARA COMPATIBILIDAD =====

    def retrieve_chroma(self, collection_name: str, id: Union[str, List[str]]) -> Union[str, List[str]]:
        """"""
        user_filtered_collections = ['owner', 'user_template', 'prospect', 
                                   'outreach', 'chat', 'temp']
        
        
      
        result = self.chroma[collection_name].get(ids=[str(id)], include=['documents'])
        
        return result['documents'][0] if result['documents'] else ""
    
  

    def close_connection(self) -> None:
        """Cierra la conexión a PostgreSQL"""
        try:
            if self.sql:
                self.sql.close()
            if self.conn:
                self.conn.close()
            print("Conexión a PostgreSQL cerrada correctamente.")
        except Exception as e:
            print(f'Error al cerrar conexión: {str(e)}')


if __name__ == '__main__':
    import time
    
    inicio = time.time()
    db = DB()
 
    db.create_tables_sql()
  
    
    print(f'\n\nTiempo de ejecución: {round(time.time()-inicio,2)} segundos.')

