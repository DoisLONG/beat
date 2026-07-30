{{/*
Expand the name of the chart.
*/}}
{{- define "reranking.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "reranking.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "reranking.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Convert chart name to a string suitable as metric prefix
*/}}
{{- define "reranking.metricPrefix" -}}
{{- include "reranking.fullname" . | replace "-" "_" | regexFind "[a-zA-Z_:][a-zA-Z0-9_:]*" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "reranking.labels" -}}
helm.sh/chart: {{ include "reranking.chart" . }}
{{ include "reranking.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "reranking.selectorLabels" -}}
app.kubernetes.io/name: {{ include "reranking.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "reranking.serviceAccountName" -}}
{{- if .Values.global.sharedSAName }}
{{- .Values.global.sharedSAName }}
{{- else if .Values.serviceAccount.create }}
{{- default (include "reranking.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
